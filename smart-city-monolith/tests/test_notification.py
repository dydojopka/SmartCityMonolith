import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.dependencies import get_notification_api
from app.modules.notification.api import NotificationApi, NotificationResponse
from app.modules.notification.models import Notification


def test_facade_send_success(notification_api, session_factory, caplog):
    caplog.set_level(logging.INFO)

    result = notification_api.send(
        user_id="00000000-0000-0000-0000-000000000001",
        channel="PUSH",
        recipient="00000000-0000-0000-0000-000000000001",
        subject="Тестовое уведомление",
        message="Текст тестового уведомления",
    )

    assert isinstance(result, NotificationResponse)
    assert result.status == "SENT"
    assert result.sent_at is not None
    assert result.created_at.tzinfo is not None
    assert result.sent_at.tzinfo is not None
    assert str(result.user_id) == "00000000-0000-0000-0000-000000000001"
    assert result.channel == "PUSH"
    assert result.recipient == "00000000-0000-0000-0000-000000000001"
    assert result.subject == "Тестовое уведомление"
    assert result.message == "Текст тестового уведомления"

    with session_factory() as session:
        db_notification = session.get(Notification, str(result.id))
        assert db_notification is not None
        assert db_notification.status == "SENT"
        assert db_notification.sent_at is not None

    messages = [record.message for record in caplog.records]
    assert any("notification_pending" in msg for msg in messages)
    assert any("notification_sent" in msg for msg in messages)
    assert not any("service-token" in msg.lower() for msg in messages)
    assert not any("authorization" in msg.lower() for msg in messages)


def test_facade_fail_sending(session_factory, caplog):
    caplog.set_level(logging.INFO)
    api = NotificationApi(session_factory, fail_sending=True)

    with pytest.raises(RuntimeError, match="Notification sending failed"):
        api.send(
            user_id=None,
            channel="EMAIL",
            recipient="test@example.com",
            subject=None,
            message="Сообщение при сбое",
        )

    with session_factory() as session:
        notification = session.scalar(
            select(Notification).order_by(Notification.created_at.desc())
        )
        assert notification is not None
        assert notification.status == "PENDING"
        assert notification.sent_at is None

    messages = [record.message for record in caplog.records]
    assert any("notification_pending" in msg for msg in messages)
    assert not any("notification_sent" in msg for msg in messages)


@pytest.mark.parametrize(
    "kwargs",
    [
        # неверный UUID
        {
            "user_id": "not-a-uuid",
            "channel": "EMAIL",
            "recipient": "test@example.com",
            "subject": None,
            "message": "msg",
        },
        # неверный channel
        {
            "user_id": None,
            "channel": "INVALID",
            "recipient": "test@example.com",
            "subject": None,
            "message": "msg",
        },
        # пустой recipient
        {
            "user_id": None,
            "channel": "EMAIL",
            "recipient": "",
            "subject": None,
            "message": "msg",
        },
        # пустой message
        {
            "user_id": None,
            "channel": "EMAIL",
            "recipient": "test@example.com",
            "subject": None,
            "message": "",
        },
        # слишком длинный message
        {
            "user_id": None,
            "channel": "EMAIL",
            "recipient": "test@example.com",
            "subject": None,
            "message": "a" * 5001,
        },
    ],
)
def test_facade_validation(notification_api, session_factory, kwargs):
    with session_factory() as session:
        initial_count = session.scalar(select(func.count()).select_from(Notification))

    with pytest.raises(ValidationError):
        notification_api.send(**kwargs)

    with session_factory() as session:
        final_count = session.scalar(select(func.count()).select_from(Notification))
    assert final_count == initial_count


def test_http_create_notification(client, service_headers):
    response = client.post(
        "/notifications",
        json={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "channel": "PUSH",
            "recipient": "00000000-0000-0000-0000-000000000001",
            "subject": "HTTP тест",
            "message": "Сообщение через HTTP",
        },
        headers=service_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SENT"
    assert data["sent_at"] is not None


def test_http_create_notification_no_token(client):
    response = client.post(
        "/notifications",
        json={
            "user_id": None,
            "channel": "EMAIL",
            "recipient": "test@example.com",
            "subject": None,
            "message": "msg",
        },
    )
    assert response.status_code == 401


def test_http_create_notification_bad_token(client):
    response = client.post(
        "/notifications",
        json={
            "user_id": None,
            "channel": "EMAIL",
            "recipient": "test@example.com",
            "subject": None,
            "message": "msg",
        },
        headers={"X-Service-Token": "wrong-token"},
    )
    assert response.status_code == 401


def test_http_create_notification_invalid_body(client, service_headers):
    response = client.post(
        "/notifications",
        json={"channel": "INVALID"},
        headers=service_headers,
    )
    assert response.status_code == 422


def test_http_fail_sending(client, session_factory, service_headers):
    def override():
        return NotificationApi(session_factory, fail_sending=True)

    client.app.dependency_overrides[get_notification_api] = override
    try:
        with TestClient(client.app, raise_server_exceptions=False) as http_client:
            response = http_client.post(
                "/notifications",
                json={
                    "user_id": None,
                    "channel": "EMAIL",
                    "recipient": "test@example.com",
                    "subject": None,
                    "message": "Сообщение при HTTP-сбое",
                },
                headers=service_headers,
            )
        assert response.status_code == 500
    finally:
        client.app.dependency_overrides.clear()

    with session_factory() as session:
        notification = session.scalar(
            select(Notification).order_by(Notification.created_at.desc())
        )
        assert notification is not None
        assert notification.status == "PENDING"
        assert notification.sent_at is None
