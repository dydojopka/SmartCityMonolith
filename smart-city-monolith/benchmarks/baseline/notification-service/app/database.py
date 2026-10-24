import os
from datetime import datetime, timezone
from collections.abc import Generator

from sqlalchemy import DateTime, create_engine, event, inspect
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notification.db")


def build_engine(url: str):
    connect_args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    result = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):
        @event.listens_for(result, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return result


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Datetime must have a timezone")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


engine = build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def schema_signature(reader, name):
    normalize = lambda value: "" if value is None else str(value).strip()
    return (
        sorted((c["name"], str(c["type"]), c["nullable"], normalize(c.get("default"))) for c in reader.get_columns(name)),
        reader.get_pk_constraint(name)["constrained_columns"],
        sorted((i["name"], bool(i["unique"]), tuple(i["column_names"]), normalize(i.get("dialect_options", {}).get("sqlite_where"))) for i in reader.get_indexes(name)),
        sorted((tuple(u["column_names"])) for u in reader.get_unique_constraints(name)),
        sorted((c["name"] or "", normalize(c["sqltext"])) for c in reader.get_check_constraints(name)),
        sorted((tuple(f["constrained_columns"]), f["referred_table"], tuple(f["referred_columns"]), repr(sorted(f.get("options", {}).items()))) for f in reader.get_foreign_keys(name)),
    )


def init_database() -> None:
    import app.models  # noqa: F401

    reference = build_engine("sqlite://")
    try:
        Base.metadata.create_all(reference)
        existing, expected = inspect(engine), inspect(reference)
        for table in Base.metadata.sorted_tables:
            if existing.has_table(table.name) and schema_signature(existing, table.name) != schema_signature(expected, table.name):
                raise RuntimeError("Legacy database: migrate a backup with scripts/migrate_database.py before starting")
    finally:
        reference.dispose()
    Base.metadata.create_all(bind=engine)
