"""Тесты модуля Utility: HTTP-адаптер + best-effort уведомление через фасад."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.dependencies import get_notification_api
from app.errors import validation_error
from app.modules.utility.models import Issue
from app.modules.utility.router import router as utility_router

USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def utility_app(clean_database):
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_error)
    app.include_router(utility_router)
    return app


@pytest.fixture
def utility_client(utility_app):
    with TestClient(utility_app) as client:
        yield client
    utility_app.dependency_overrides.clear()


def _payload(**overrides):
    base = {
        "title": "Не работает фонарь",
        "description": "Не включается вечером",
        "category": "lighting",
        "address": "Невский проспект, 10",
    }
    base.update(overrides)
    return base


# ---------- Создание заявки ----------


def test_create_issue(utility_client, user_headers, session_factory):
    response = utility_client.post("/issues", json=_payload(), headers=user_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "NEW"
    assert body["category"] == "LIGHTING"  # нормализация
    assert body["user_id"] == USER_ID
    with session_factory() as session:
        stored = session.get(Issue, body["id"])
        assert stored is not None
        assert stored.title == "Не работает фонарь"


def test_create_issue_requires_jwt(utility_client):
    assert utility_client.post("/issues", json=_payload()).status_code == 401


def test_create_issue_invalid_payload(utility_client, user_headers):
    response = utility_client.post("/issues", json={"title": "x"}, headers=user_headers)
    assert response.status_code == 422


def test_create_issue_idempotent(utility_client, user_headers):
    headers = {**user_headers, "X-Idempotency-Key": "key-1"}
    first = utility_client.post("/issues", json=_payload(), headers=headers)
    assert first.status_code == 201
    second = utility_client.post("/issues", json=_payload(), headers=headers)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_create_issue_idempotency_conflict(utility_client, user_headers):
    headers = {**user_headers, "X-Idempotency-Key": "key-2"}
    utility_client.post("/issues", json=_payload(), headers=headers)
    other = _payload(title="Другая проблема")
    response = utility_client.post("/issues", json=other, headers=headers)
    assert response.status_code == 409


# ---------- Список заявок ----------


def test_list_issues_user_sees_only_own(
    utility_client, user_headers, operator_headers, session_factory
):
    with session_factory() as session:
        session.add(
            Issue(
                id="aaaaaaaa-0000-0000-0000-000000000001",
                user_id=OTHER_USER_ID,
                title="Чужая заявка",
                description="Описание",
                category="OTHER",
                address="Адрес",
                status="NEW",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    assert (
        utility_client.post("/issues", json=_payload(), headers=user_headers).status_code
        == 201
    )

    user_list = utility_client.get("/issues", headers=user_headers).json()
    assert all(item["user_id"] == USER_ID for item in user_list)
    assert all(item["id"] != "aaaaaaaa-0000-0000-0000-000000000001" for item in user_list)

    operator_list = utility_client.get("/issues", headers=operator_headers).json()
    ids = {item["id"] for item in operator_list}
    assert "aaaaaaaa-0000-0000-0000-000000000001" in ids


# ---------- Смена статуса + уведомление ----------


def test_update_status_sends_notification(
    utility_client, utility_app, user_headers, operator_headers
):
    issue_id = utility_client.post(
        "/issues", json=_payload(), headers=user_headers
    ).json()["id"]

    fake_api = MagicMock()
    utility_app.dependency_overrides[get_notification_api] = lambda: fake_api

    response = utility_client.put(
        f"/issues/{issue_id}",
        json={"status": "IN_PROGRESS"},
        headers=operator_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"
    fake_api.send.assert_called_once()
    kwargs = fake_api.send.call_args.kwargs
    assert kwargs["channel"] == "PUSH"
    assert kwargs["user_id"] == USER_ID
    assert kwargs["recipient"] == USER_ID


def test_update_status_notifies_issue_owner(
    utility_client, utility_app, token_for, operator_headers
):
    other_headers = {
        "Authorization": f"Bearer {token_for('USER', OTHER_USER_ID)}"
    }
    issue_id = utility_client.post(
        "/issues", json=_payload(), headers=other_headers
    ).json()["id"]

    fake_api = MagicMock()
    utility_app.dependency_overrides[get_notification_api] = lambda: fake_api

    response = utility_client.put(
        f"/issues/{issue_id}",
        json={"status": "RESOLVED"},
        headers=operator_headers,
    )
    assert response.status_code == 200
    fake_api.send.assert_called_once()
    assert fake_api.send.call_args.kwargs["user_id"] == OTHER_USER_ID


def test_update_status_failure_keeps_issue_saved(
    utility_client, utility_app, user_headers, operator_headers, session_factory
):
    issue_id = utility_client.post(
        "/issues", json=_payload(), headers=user_headers
    ).json()["id"]

    fake_api = MagicMock()
    fake_api.send.side_effect = RuntimeError("Notification sending failed")
    utility_app.dependency_overrides[get_notification_api] = lambda: fake_api

    response = utility_client.put(
        f"/issues/{issue_id}",
        json={"status": "RESOLVED"},
        headers=operator_headers,
    )
    # Клиент получает 200 — заявка уже сохранена, уведомление — best-effort.
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"
    with session_factory() as session:
        assert session.get(Issue, issue_id).status == "RESOLVED"


def test_update_status_no_change_no_notification(
    utility_client, utility_app, user_headers, operator_headers
):
    issue_id = utility_client.post(
        "/issues", json=_payload(), headers=user_headers
    ).json()["id"]

    fake_api = MagicMock()
    utility_app.dependency_overrides[get_notification_api] = lambda: fake_api

    # NEW -> NEW: UPDATE не изменит строку, уведомление не отправляется.
    response = utility_client.put(
        f"/issues/{issue_id}", json={"status": "NEW"}, headers=operator_headers
    )
    assert response.status_code == 200
    fake_api.send.assert_not_called()


def test_update_status_forbidden_for_user(utility_client, user_headers):
    issue_id = utility_client.post(
        "/issues", json=_payload(), headers=user_headers
    ).json()["id"]
    response = utility_client.put(
        f"/issues/{issue_id}", json={"status": "RESOLVED"}, headers=user_headers
    )
    assert response.status_code == 403


def test_update_status_not_found(utility_client, operator_headers):
    response = utility_client.put(
        "/issues/00000000-0000-0000-0000-000000000000",
        json={"status": "RESOLVED"},
        headers=operator_headers,
    )
    assert response.status_code == 404