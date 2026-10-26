import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, TypeAdapter
from sqlalchemy import Column, Integer, MetaData, Table, inspect, select, text
from sqlalchemy.exc import StatementError

from app.auth import CurrentUser, get_current_user, require_roles
from app import database
from app.database import UTCDateTime, build_engine, get_db
from app.errors import validation_error
from app.init_db import init_database


def test_health_and_docs(client):
    assert client.get("/health").json() == {"status": "ok", "service": "smart-city-monolith"}
    assert client.get("/docs").status_code == 200


def test_cors(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.fixture
def auth_client():
    probe = FastAPI()
    probe.add_exception_handler(RequestValidationError, validation_error)

    @probe.get("/protected")
    def protected(user: Annotated[CurrentUser, Depends(get_current_user)]):
        return {"id": user.id, "role": user.role}

    @probe.get("/operator")
    def operator(user: Annotated[CurrentUser, Depends(require_roles("OPERATOR", "ADMIN"))]):
        return {"role": user.role}

    class Payload(BaseModel):
        value: int = Field(gt=0)

    @probe.post("/payload")
    def payload(body: Payload):
        return body

    with TestClient(probe) as test_client:
        yield test_client


def test_missing_jwt(auth_client):
    response = auth_client.get("/protected")
    assert response.status_code == 401
    assert response.json() == {"detail": "Требуется JWT"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("role", ["USER", "OPERATOR", "ADMIN"])
def test_valid_jwt(auth_client, token_for, role):
    response = auth_client.get("/protected", headers={"Authorization": f"Bearer {token_for(role)}"})
    assert response.status_code == 200
    assert response.json() == {"id": "00000000-0000-0000-0000-000000000001", "role": role}


@pytest.mark.parametrize(
    "changes",
    [
        {"sub": "not-a-uuid"},
        {"sub": None},
        {"role": "SUPERUSER"},
        {"role": ["ADMIN"]},
        {"exp": 1},
        {"sub": None, "role": None},
    ],
)
def test_invalid_claims(auth_client, changes):
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "role": "USER",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    payload.update(changes)
    token = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    response = auth_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Недействительный JWT"}


@pytest.mark.parametrize("claim", ["sub", "role", "exp"])
def test_required_jwt_claims(auth_client, claim):
    payload = {"sub": "00000000-0000-0000-0000-000000000001", "role": "USER", "exp": 9999999999}
    del payload[claim]
    token = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    assert auth_client.get("/protected", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("algorithm, secret", [("HS256", "wrong-secret"), ("HS384", "test-only-jwt-secret")])
def test_wrong_signature_or_algorithm(auth_client, algorithm, secret):
    token = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000001", "role": "ADMIN", "exp": 9999999999},
        secret,
        algorithm=algorithm,
    )
    assert auth_client.get("/protected", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("role, expected", [("USER", 403), ("OPERATOR", 200), ("ADMIN", 200)])
def test_roles(auth_client, token_for, role, expected):
    response = auth_client.get("/operator", headers={"Authorization": f"Bearer {token_for(role)}"})
    assert response.status_code == expected
    if expected == 403:
        assert response.json() == {"detail": "Недостаточно прав"}


def test_validation_errors_hide_input_and_context(auth_client):
    response = auth_client.post("/payload", json={"value": -123})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["body", "value"]
    assert all("input" not in error and "ctx" not in error for error in detail)


def test_database_is_a_private_file(db_engine, tmp_path):
    assert db_engine is database.engine
    assert Path(db_engine.url.database) == tmp_path / "monolith-test.db"
    with db_engine.connect() as connection:
        files = [row for row in connection.execute(text("PRAGMA database_list"))
                 if row[1] != "temp"]
    assert len(files) == 1
    assert Path(files[0][2]) == tmp_path / "monolith-test.db"


def test_external_database_urls_cannot_select_test_storage(tmp_path):
    working_file = tmp_path / "working.db"
    with sqlite3.connect(working_file) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES ('keep')")
    environment = os.environ | {
        "DATABASE_URL": f"sqlite:///{working_file}",
        "TEST_DATABASE_URL": f"sqlite:///{working_file}",
    }
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_infrastructure.py::test_health_and_docs"],
        cwd=Path(__file__).resolve().parents[1], env=environment,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(working_file) as connection:
        assert connection.execute("SELECT value FROM sentinel").fetchall() == [("keep",)]


@pytest.mark.parametrize("url", ["postgresql://localhost/demo", "mysql://localhost/demo", "sqlite+aiosqlite://"])
def test_engine_rejects_other_database_drivers(url):
    with pytest.raises(ValueError, match="SQLite"):
        build_engine(url)


def test_sqlite_settings_match_the_source(db_engine):
    with db_engine.connect() as first, db_engine.connect() as second:
        for connection in (first, second):
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert connection.scalar(text("PRAGMA busy_timeout")) == 30000
            assert connection.scalar(text("PRAGMA journal_mode")) == "delete"


@pytest.fixture
def probe_table(db_engine):
    table = Table(
        "utility_infrastructure_probe",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("created_at", UTCDateTime(), nullable=False),
    )
    table.create(db_engine)
    return table


def test_init_database_is_idempotent_and_preserves_rows(db_engine, probe_table):
    instant = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    with db_engine.begin() as connection:
        connection.execute(probe_table.insert().values(id=1, created_at=instant))
    init_database()
    init_database()
    assert "utility_infrastructure_probe" in inspect(db_engine).get_table_names()
    with db_engine.connect() as connection:
        assert connection.execute(select(probe_table.c.created_at)).scalar_one() == instant


def test_sqlite_utc_round_trip(db_engine, probe_table):
    instant = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=3)))
    with db_engine.begin() as connection:
        connection.execute(probe_table.insert().values(id=1, created_at=instant))
        actual = connection.scalar(select(probe_table.c.created_at))
        stored = connection.scalar(text("SELECT created_at FROM utility_infrastructure_probe"))
    assert actual == instant
    assert actual.utcoffset() == timedelta(0)
    assert stored == "2026-01-02 00:04:05.000000"
    assert TypeAdapter(datetime).dump_json(actual).endswith(b'Z"')


def test_naive_datetime_rejected(db_engine, probe_table):
    with pytest.raises(StatementError, match="Datetime must have a timezone"):
        with db_engine.begin() as connection:
            connection.execute(probe_table.insert().values(id=1, created_at=datetime(2026, 1, 2)))


def test_get_db_closes_and_rolls_back_uncommitted_work(db_engine, probe_table):
    dependency = get_db()
    session = next(dependency)
    session.execute(probe_table.insert().values(id=1, created_at=datetime.now(timezone.utc)))
    dependency.close()
    with db_engine.connect() as connection:
        assert connection.execute(select(probe_table)).all() == []


def test_independent_sessions_share_committed_data(session_factory, probe_table):
    instant = datetime.now(timezone.utc)
    with session_factory() as writer:
        writer.execute(probe_table.insert().values(id=1, created_at=instant))
        writer.commit()
    with session_factory() as reader:
        assert reader.scalar(select(probe_table.c.created_at)) == instant


def test_concurrent_conditional_updates_use_the_same_file(session_factory, probe_table):
    with session_factory() as session:
        session.execute(probe_table.insert().values(id=1, created_at=datetime.now(timezone.utc)))
        session.commit()

    def update_once(_):
        with session_factory() as session:
            result = session.execute(probe_table.update().where(probe_table.c.id == 1).values(id=2))
            session.commit()
            return result.rowcount

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(update_once, range(2))) == [0, 1]
    with session_factory() as session:
        assert session.scalars(select(probe_table.c.id)).all() == [2]
