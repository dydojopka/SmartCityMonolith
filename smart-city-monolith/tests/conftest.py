import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL

# При импорте приложения engine не должен указывать на внешнюю рабочую БД.
# Каждый тест ниже получает собственный реальный файл, а не эту in-memory БД.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-only-jwt-secret"
os.environ["SERVICE_TOKEN"] = "test-only-service-token"
os.environ["NOTIFICATION_FAIL_SEND"] = "false"

from app import database
from app.database import SessionLocal
from app.init_db import init_database
from app.main import app

USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True)
def clean_database(tmp_path, monkeypatch):
    url = URL.create("sqlite", database=str(tmp_path / "monolith-test.db"))
    test_engine = database.build_engine(url.render_as_string())
    previous_bind = SessionLocal.kw["bind"]
    monkeypatch.setattr(database, "engine", test_engine)
    SessionLocal.configure(bind=test_engine)
    try:
        init_database()
        yield test_engine
    finally:
        test_engine.dispose()
        SessionLocal.configure(bind=previous_bind)


@pytest.fixture
def db_engine(clean_database):
    return clean_database


@pytest.fixture
def session_factory(clean_database):
    return SessionLocal


@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def client(clean_database):
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def notification_api(clean_database):
    from app.dependencies import get_notification_api

    return get_notification_api()


@pytest.fixture
def token_for():
    def create_token(role="USER", user_id=USER_ID, *, expires_in=3600):
        return jwt.encode(
            {
                "sub": user_id,
                "role": role,
                "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            },
            os.environ["JWT_SECRET"],
            algorithm="HS256",
        )

    return create_token


@pytest.fixture
def user_headers(token_for):
    return {"Authorization": f"Bearer {token_for()}"}


@pytest.fixture
def operator_headers(token_for):
    return {"Authorization": f"Bearer {token_for('OPERATOR')}"}


@pytest.fixture
def admin_headers(token_for):
    return {"Authorization": f"Bearer {token_for('ADMIN')}"}


@pytest.fixture
def service_headers():
    return {"X-Service-Token": os.environ["SERVICE_TOKEN"]}
