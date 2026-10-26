"""Измерение Utility -> Notification с проверкой каждой записи в SQLite."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import threading
import time
from uuid import uuid4

import httpx
import jwt


READ_DATABASE = '''
import json, sqlite3, sys
data = json.load(sys.stdin)
with sqlite3.connect("file:" + data["path"] + "?mode=ro", uri=True) as db:
    db.row_factory = sqlite3.Row
    rows = [dict(row) for row in db.execute(
        "SELECT * FROM " + data["table"] + " WHERE user_id = ?", (data["user_id"],))]
print(json.dumps(rows, ensure_ascii=False))
'''

FINGERPRINT = '''
import importlib.metadata, json, platform, sqlite3
from app import database
with database.engine.connect() as connection:
    settings = {key: connection.exec_driver_sql("PRAGMA " + key).scalar()
                for key in ("foreign_keys", "busy_timeout", "journal_mode", "synchronous")}
print(json.dumps({"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
    "settings": settings, "packages": {dist.metadata["Name"].lower(): dist.version
    for dist in importlib.metadata.distributions()}}))
'''


def command(args, *, stdin=None):
    return subprocess.run(args, input=stdin, text=True, encoding="utf-8", capture_output=True,
                          check=True, timeout=120).stdout.strip()


class Stand:
    def __init__(self, args):
        self.args = args
        self.docker = args.docker_command
        self.services = ["utility-service", "notification-service"] if args.version == "micro" else ["app"]
        self.compose = self.docker + ["compose", "--env-file", os.devnull, "-p", args.project,
                                      "-f", str(args.compose.resolve())]
        self.containers = [command(self.compose + ["ps", "-q", service]) for service in self.services]
        if any(not value or "\n" in value for value in self.containers):
            raise ValueError("Each selected service must have exactly one running container")
        self.fingerprints = {service: json.loads(command(self.docker + ["exec", container,
                            "python", "-c", FINGERPRINT]))
                             for service, container in zip(self.services, self.containers)}

    def rows(self, kind, user_id):
        micro = self.args.version == "micro"
        container = self.containers[0 if kind == "issues" or not micro else 1]
        path = f"/data/{'utility' if kind == 'issues' else 'notification'}.db" if micro else "/data/monolith.db"
        table = kind if micro else ("utility_issues" if kind == "issues" else "notification_notifications")
        return json.loads(command(self.docker + ["exec", "-i", container, "python", "-c", READ_DATABASE],
                                   stdin=json.dumps({"path": path, "table": table, "user_id": user_id})))

    def verify(self, ids, user_id, *, changed):
        selected = set(ids)
        issues = {row["id"]: row for row in self.rows("issues", user_id) if row["id"] in selected}
        messages = {f"Заявка {issue_id} получила статус IN_PROGRESS" for issue_id in ids}
        notifications = [row for row in self.rows("notifications", user_id) if row["message"] in messages]
        expected_status = "IN_PROGRESS" if changed else "NEW"
        assert len(issues) == len(ids) and all(row["status"] == expected_status for row in issues.values())
        assert len(notifications) == (len(ids) if changed else 0)
        if changed:
            assert {row["message"] for row in notifications} == messages
            assert all(row["status"] == "SENT" and row["sent_at"] is not None
                       and row["channel"] == "PUSH" and row["user_id"] == row["recipient"] == user_id
                       and row["subject"] == "Статус заявки изменён" for row in notifications)
        return {"issues": len(issues), "notifications": len(notifications), "all_sent": changed}


def memory_bytes(value):
    amount, unit = re.fullmatch(r"([0-9.]+)\s*([A-Za-z]+)", value.split(" / ")[0]).groups()
    return float(amount) * {"B": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9,
                           "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}[unit]


class MemorySampler:
    def __init__(self, stand):
        self.stand = stand
        self.samples = []
        self.errors = []
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self.collect, daemon=True)

    def collect(self):
        while not self.stop.is_set():
            start = time.perf_counter()
            try:
                raw = command(self.stand.docker + ["stats", "--no-stream", "--format", "{{json .}}",
                                                  *self.stand.containers])
                rows = [json.loads(line) for line in raw.splitlines()]
                assert len(rows) == len(self.stand.containers)
                self.samples.append({"start": start, "end": time.perf_counter(),
                    "containers": [{"id": row["ID"], "memory": row["MemUsage"]} for row in rows],
                    "total_mb": sum(memory_bytes(row["MemUsage"]) for row in rows) / 1e6})
            except Exception as error:
                self.errors.append(type(error).__name__)
            finally:
                self.ready.set()


def token(secret, user_id, role):
    return jwt.encode({"sub": user_id, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=4)}, secret, algorithm="HS256")


def run_once(stand, number, secret):
    args = stand.args
    user_id = str(uuid4())
    user_headers = {"Authorization": "Bearer " + token(secret, user_id, "USER")}
    operator_headers = {"Authorization": "Bearer " + token(secret, user_id, "OPERATOR")}
    with httpx.Client(base_url=args.url, timeout=60, trust_env=False,
                      limits=httpx.Limits(max_connections=10, max_keepalive_connections=10)) as client:
        ids = []
        for index in range(args.requests + 20):
            response = client.post("/issues", headers=user_headers, json={
                "title": f"Замер {number}, заявка {index}", "description": "Тестовая заявка для измерения",
                "category": "LIGHTING", "address": "Тестовая улица, 10"})
            assert response.status_code == 201 and response.json()["status"] == "NEW"
            ids.append(response.json()["id"])

        def update(issue_id):
            start = time.perf_counter()
            try:
                response = client.put(f"/issues/{issue_id}", headers=operator_headers,
                                      json={"status": "IN_PROGRESS"})
                elapsed = time.perf_counter() - start
                body = response.json()
                valid = response.status_code == 200 and body.get("id") == issue_id and body.get("status") == "IN_PROGRESS"
                return {"issue_id": issue_id, "latency_ms": elapsed * 1000,
                        "status_code": response.status_code, "valid": valid}
            except Exception as error:
                return {"issue_id": issue_id, "latency_ms": (time.perf_counter() - start) * 1000,
                        "status_code": None, "valid": False, "error": type(error).__name__}

        for issue_id in ids[:20]:
            assert update(issue_id)["valid"]
        stand.verify(ids[:20], user_id, changed=True)
        measured = ids[20:]
        before = stand.verify(measured, user_id, changed=False)
        sampler = MemorySampler(stand)
        sampler.thread.start()
        assert sampler.ready.wait(120), "Memory sampler did not start"
        with ThreadPoolExecutor(max_workers=10) as pool:
            start = time.perf_counter()
            responses = list(pool.map(update, measured))
            end = time.perf_counter()
        sampler.stop.set()
        sampler.thread.join(timeout=130)
        try:
            after = stand.verify(measured, user_id, changed=True)
        except AssertionError:
            after = {"verification_failed": True}
        samples = [{**row, "start": row["start"] - start, "end": row["end"] - start}
                   for row in sampler.samples]
        during = [row for row in samples if row["start"] >= 0 and row["end"] <= end - start]
        valid = (all(row["valid"] for row in responses) and len(during) >= 2
                 and not sampler.errors and not after.get("verification_failed"))
        return {"run": number, "valid": valid, "user_id": user_id, "n": args.requests,
                "warmup": 20, "concurrency": 10, "elapsed_seconds": end - start,
                "latency_ms": statistics.mean(row["latency_ms"] for row in responses),
                "rps": args.requests / (end - start),
                "memory_mb": statistics.mean(row["total_mb"] for row in during) if during else None,
                "memory_rule": "Arithmetic mean of summed Docker working-set memory, complete samples inside timed batch; MB=10^6 bytes",
                "memory_sample_errors": sampler.errors, "samples_during_load": len(during),
                "memory_samples": samples, "before": before, "after": after, "requests": responses}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("micro", "mono"), required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--compose", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--docker-command", nargs="+", default=["docker"])
    args = parser.parse_args()
    if args.requests < 200 or args.runs < 1:
        parser.error("requests must be >= 200 and runs >= 1")
    secret = os.environ.get("JWT_SECRET", "development-jwt-secret")
    stand = Stand(args)
    data = {"version": args.version, "revision": args.revision,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "Utility + Notification only", "containers": len(stand.containers),
            "startup_commands": 1, "client_python": platform.python_version(),
            "client_os": platform.system(), "client_httpx": importlib.metadata.version("httpx"),
            "docker_server": command(stand.docker + ["version", "--format", "{{.Server.Version}}"]),
            "docker_host": json.loads(command(stand.docker + ["info", "--format", "{{json .}}"])),
            "fingerprints": stand.fingerprints, "runs": []}
    data["cpu_model"] = platform.processor()
    if Path("/proc/cpuinfo").exists():
        data["cpu_model"] = next(line.split(":", 1)[1].strip() for line in
                                 Path("/proc/cpuinfo").read_text().splitlines()
                                 if line.startswith("model name"))
    data["images"] = [json.loads(command(stand.docker + ["inspect", "--format",
                      '{{json .Config.Cmd}}', container])) for container in stand.containers]
    data["docker_host"] = {key: data["docker_host"][key] for key in
                            ("NCPU", "MemTotal", "OperatingSystem", "OSType", "Architecture", "KernelVersion")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for number in range(1, args.runs + 1):
        result = run_once(stand, number, secret)
        data["runs"].append(result)
        data["valid"] = len(data["runs"]) == args.runs and all(row["valid"] for row in data["runs"])
        if data["valid"]:
            data["means"] = {key: statistics.mean(row[key] for row in data["runs"])
                             for key in ("latency_ms", "rps", "memory_mb")}
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: result[key] for key in
                         ("run", "valid", "latency_ms", "rps", "memory_mb", "samples_during_load")}), flush=True)
        if not result["valid"]:
            raise SystemExit("Invalid measurement: inspect evidence and repeat both versions at the same larger N")


if __name__ == "__main__":
    main()
