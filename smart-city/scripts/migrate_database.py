"""Copy ONE service's legacy SQLite into a new validated database; never overwrite.

Run with that service's requirements installed. Stop the service before installing
the result into its volume. UTC assumptions and unknown sensor/vehicle metadata
must be explicitly supplied. No cross-service models are imported.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import sys
import tempfile
from uuid import UUID, NAMESPACE_URL, uuid5


def migrate(service, source, destination, mapping, assume_utc):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "services" / f"{service}-service"))
    from app.database import Base, build_engine
    import app.models  # noqa: F401
    from sqlalchemy import Boolean, Date, DateTime, JSON

    if not source.is_file() or destination.exists() or destination.with_suffix(".migration.json").exists():
        raise ValueError("Source must exist; destination must NOT exist")
    transforms = []
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if names - set(Base.metadata.tables):
            raise ValueError(f"Unknown tables must be reviewed first: {names - set(Base.metadata.tables)}")
        removed = {"sensor_readings": {"created_at"}} if service == "environment" else {}
        for name in names:
            columns = {row[1] for row in db.execute(f'PRAGMA table_xinfo("{name}")')}
            unknown = columns - set(Base.metadata.tables[name].columns.keys()) - removed.get(name, set())
            if unknown:
                raise ValueError(f"Unknown columns require explicit review: {name}: {sorted(unknown)}")
            for column in columns & removed.get(name, set()):
                transforms.append({"table": name, "source": column, "destination": "received_at"})
        rows = {name: [dict(r) for r in db.execute(f'SELECT * FROM "{name}"')] for name in names}
    ids = {}

    def identifier(table, value):
        try:
            result = str(UUID(str(value)))
        except ValueError:
            result = str(uuid5(NAMESPACE_URL, f"smart-city:{service}:{table}:{value}"))
        ids[f"{table}:{value}"] = result
        return result

    if service == "environment":
        from app.seed import DEMO_SENSORS
        demo_names = {"Температура воздуха": DEMO_SENSORS[0], "Влажность воздуха": DEMO_SENSORS[1]}
        for sensor in rows.get("sensors", []):
            old = sensor["id"]
            supplied = mapping.get("sensors", {}).get(str(old), {})
            defaults = demo_names.get(sensor["name"], {})
            for key in ("unit", "latitude", "longitude"):
                if key not in sensor:
                    if key not in supplied and key not in defaults:
                        raise ValueError(f"Sensor {old} requires explicit mapping for {key}")
                    sensor[key] = supplied.get(key, defaults.get(key))
            try:
                sensor["id"] = str(UUID(str(supplied.get("id", old))))
            except ValueError:
                sensor["id"] = supplied.get("id", defaults.get("id", identifier("sensors", old)))
            ids[f"sensors:{old}"] = sensor["id"]
            if not sensor.get("api_key_hash"):
                key = os.getenv("SENSOR_API_KEY")
                if not key:
                    raise ValueError("Set SENSOR_API_KEY to the legacy sensor key (it is never printed)")
                sensor["api_key_hash"] = sha256(key.encode()).hexdigest()
            if sensor["status"] == "MAINTENANCE": sensor["status"] = "INACTIVE"
        for reading in rows.get("sensor_readings", []):
            reading["sensor_id"] = ids[f"sensors:{reading['sensor_id']}"]
            reading["received_at"] = reading.get("received_at", reading.get("created_at"))
            if not math.isfinite(float(reading["value"])):
                raise ValueError(f"Nonfinite sensor reading {reading['id']}: quarantine/review the original; nothing overwritten")

    if service == "transport":
        for vehicle in rows.get("vehicles", []):
            if "type" not in vehicle or "route_number" not in vehicle:
                supplied = mapping.get("vehicles", {}).get(vehicle["id"], {})
                if not {"type", "route_number"} <= supplied.keys():
                    raise ValueError(f"Vehicle {vehicle['id']} requires explicit type/route_number mapping; no invented routes")
                vehicle.update(supplied)
            vehicle["updated_at"] = vehicle.get("updated_at", vehicle.get("created_at"))
            vehicle["status"] = {"AVAILABLE": "ACTIVE", "IN_USE": "ACTIVE"}.get(vehicle["status"], vehicle["status"])

    if service == "billing":
        payments = {r["id"]: r for r in rows.get("payments", [])}
        active = Counter()
        for payment in payments.values():
            payment["status"] = {"PENDING": "CREATED", "SUCCESS": "SUCCEEDED"}.get(payment["status"], payment["status"])
            if payment["status"] in {"CREATED", "SUCCEEDED"}: active[identifier("invoices", payment["invoice_id"])] += 1
        if any(n > 1 for n in active.values()):
            raise ValueError("Multiple active/successful payments: reconcile manually; financial history was not discarded")
        for invoice in rows.get("invoices", []):
            if invoice["status"] == "UNPAID": invoice["status"] = "PENDING"
            if invoice.get("due_date"): invoice["due_date"] = str(invoice["due_date"])[:10]
            if invoice["status"] == "PAID" and not invoice.get("paid_at"):
                paid = [p for p in payments.values() if identifier("invoices", p["invoice_id"]) == identifier("invoices", invoice["id"]) and p["status"] == "SUCCEEDED"]
                if len(paid) != 1: raise ValueError(f"Paid invoice {invoice['id']} has no unambiguous payment history")
                invoice["paid_at"] = paid[0]["updated_at"]
        for event in rows.get("webhook_events", []):
            payload = event.get("payload")
            if isinstance(payload, str): payload = json.loads(payload)
            event["payload"] = payload
            if not event.get("payment_id"):
                event["payment_id"] = (payload or {}).get("payment_id")
                if event["payment_id"] is None: raise ValueError(f"Unbound webhook {event['id']}")

    # Normalize parents before any local FK. Preserve the special legacy sensor map.
    for table in Base.metadata.sorted_tables:
        for row in rows.get(table.name, []):
            if f"{table.name}:{row['id']}" not in ids:
                identifier(table.name, row["id"])

    def boolean(value):
        if type(value) in (int, bool) and value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in {"true", "false", "0", "1"}:
            return value.strip().lower() in {"true", "1"}
        raise ValueError("Ambiguous legacy Boolean; review without reactivating accounts")

    converted = {}
    for table in Base.metadata.sorted_tables:
        converted[table.name] = []
        for original in rows.get(table.name, []):
            row = {key: value for key, value in original.items() if key in table.columns}
            row["id"] = ids[f"{table.name}:{row['id']}"]
            for column in table.columns:
                value = row.get(column.name)
                if value is None: continue
                if column.name == "user_id": row[column.name] = str(UUID(str(value)))
                for fk in column.foreign_keys:
                    key = f"{fk.column.table.name}:{value}"
                    row[column.name] = ids[key] if key in ids else str(UUID(str(value)))
                if isinstance(column.type, DateTime) or column.type.__class__.__name__ == "UTCDateTime":
                    value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    if value.tzinfo is None:
                        if not assume_utc: raise ValueError("Legacy naive timestamps require --assume-legacy-utc")
                        value = value.replace(tzinfo=timezone.utc)
                    row[column.name] = value.astimezone(timezone.utc)
                elif isinstance(column.type, Date): row[column.name] = date.fromisoformat(str(value)[:10])
                elif isinstance(column.type, Boolean): row[column.name] = boolean(value)
                elif isinstance(column.type, JSON) and isinstance(value, str): row[column.name] = json.loads(value)
            converted[table.name].append(row)

    if service == "billing":
        from app.invariants import validate_invoice, validate_payment
        invoices = {r["id"]: SimpleNamespace(paid_at=None, **{k: v for k, v in r.items() if k != "paid_at"}) for r in converted["invoices"]}
        for row in converted["invoices"]:
            invoices[row["id"]].paid_at = row.get("paid_at")
        payments = {r["id"]: SimpleNamespace(**r) for r in converted["payments"]}
        for invoice in invoices.values():
            validate_invoice(invoice)
            successful = [p for p in payments.values() if p.invoice_id == invoice.id and p.status == "SUCCEEDED"]
            if invoice.status == "PAID" and len(successful) != 1:
                raise ValueError("Paid invoice requires one unambiguous successful payment")
        for payment in payments.values():
            if payment.invoice_id not in invoices:
                raise ValueError("Payment has no invoice")
            validate_payment(payment, invoices[payment.invoice_id])
        for event in converted["webhook_events"]:
            payment = payments.get(event["payment_id"])
            if payment is None or payment.status != "SUCCEEDED":
                raise ValueError("Success event requires a successful payment")
            payload = event.get("payload")
            if payload is None:
                raise ValueError("Success event payload requires explicit review")
            if payload is not None:
                if not isinstance(payload, dict):
                    raise ValueError("Webhook payload must be an object")
                if payload.get("payment_id") is not None:
                    old = payload["payment_id"]
                    key = f"payments:{old}"
                    normalized = ids[key] if key in ids else str(UUID(str(old)))
                    if normalized != event["payment_id"]:
                        raise ValueError("Webhook payload and payment binding disagree")
                    payload["payment_id"] = normalized

    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".db")
    os.close(fd)
    engine = build_engine(f"sqlite:///{temporary}")
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as db:
            for table in Base.metadata.sorted_tables:
                for row in converted[table.name]: db.execute(table.insert().values(**row))
            assert not db.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            assert db.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
        engine.dispose()
        # Exclusive creation protects an existing destination even if it appeared meanwhile.
        os.link(temporary, destination)
        report = {"service": service, "source": str(source), "legacy_naive_assumed_utc": assume_utc, "id_mapping": ids, "column_transforms": transforms, "rows": {name: len(data) for name, data in converted.items()}}
        destination.with_suffix(".migration.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report["rows"]))
    finally:
        engine.dispose()
        Path(temporary).unlink(missing_ok=True)


def main():
    from sqlalchemy.exc import SQLAlchemyError
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=["identity", "utility", "transport", "billing", "environment", "notification"])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--mapping", type=Path, help="Explicit JSON sensor/vehicle metadata mapping")
    parser.add_argument("--assume-legacy-utc", action="store_true")
    args = parser.parse_args()
    try:
        migrate(args.service, args.source, args.destination, json.loads(args.mapping.read_text()) if args.mapping else {}, args.assume_legacy_utc)
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f"Migration stopped safely: {error}\n")
    except SQLAlchemyError:
        parser.exit(1, "Migration stopped safely: legacy rows violate constraints. Review the backup; SQL parameters/secrets are not printed.\n")


if __name__ == "__main__":
    main()
