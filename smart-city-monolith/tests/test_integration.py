"""Проверки общего приложения на отдельном дисковом SQLite-файле."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.dependencies import get_notification_api
from app.init_db import init_database
from app.modules.notification.api import NotificationApi
from app.modules.notification.models import Notification
from app.modules.utility.models import Issue


def payload(**changes):
    return {"title": "Не работает фонарь", "description": "Фонарь не включается",
            "category": " lighting ", "address": " Улица Мира, 10 ", **changes}


def notifications(session_factory, issue_id):
    with session_factory() as session:
        return list(session.scalars(select(Notification).where(
            Notification.message == f"Заявка {issue_id} получила статус IN_PROGRESS"
        )))


def test_real_facade_and_noop(client, user_headers, operator_headers, session_factory):
    created = client.post("/issues", headers=user_headers, json=payload())
    assert created.status_code == 201
    issue = created.json()
    assert issue["created_at"].endswith("Z")
    assert issue["category"] == "LIGHTING"
    assert issue["address"] == "Улица Мира, 10"
    assert "request_key" not in issue
    for _ in range(2):
        response = client.put(f"/issues/{issue['id']}", headers=operator_headers,
                              json={"status": "IN_PROGRESS"})
        assert response.status_code == 200
        assert response.json()["status"] == "IN_PROGRESS"
    rows = notifications(session_factory, issue["id"])
    assert len(rows) == 1
    notification = rows[0]
    assert notification.user_id == notification.recipient == issue["user_id"]
    assert notification.subject == "Статус заявки изменён"
    assert notification.channel == "PUSH"
    assert notification.status == "SENT" and notification.sent_at is not None


def test_failure_then_recovery_on_new_issue(
    client, user_headers, operator_headers, session_factory, monkeypatch, caplog
):
    monkeypatch.setenv("NOTIFICATION_FAIL_SEND", "true")
    issue_id = client.post("/issues", headers=user_headers, json=payload()).json()["id"]
    response = client.put(f"/issues/{issue_id}", headers=operator_headers,
                          json={"status": "IN_PROGRESS"})
    assert response.status_code == 200
    with session_factory() as session:
        assert session.get(Issue, issue_id).status == "IN_PROGRESS"
    rows = notifications(session_factory, issue_id)
    assert len(rows) == 1 and rows[0].status == "PENDING" and rows[0].sent_at is None
    assert "notification_failed" in caplog.text
    monkeypatch.setenv("NOTIFICATION_FAIL_SEND", "false")
    assert client.put(f"/issues/{issue_id}", headers=operator_headers,
                      json={"status": "IN_PROGRESS"}).status_code == 200
    assert len(notifications(session_factory, issue_id)) == 1
    recovered_id = client.post("/issues", headers=user_headers, json=payload()).json()["id"]
    assert client.put(f"/issues/{recovered_id}", headers=operator_headers,
                      json={"status": "IN_PROGRESS"}).status_code == 200
    recovered = notifications(session_factory, recovered_id)
    assert len(recovered) == 1 and recovered[0].status == "SENT"


def test_parallel_status_change_sends_once(client, user_headers, operator_headers, session_factory):
    issue_id = client.post("/issues", headers=user_headers, json=payload()).json()["id"]
    barrier = Barrier(10)

    def update(_):
        barrier.wait(timeout=10)
        return client.put(f"/issues/{issue_id}", headers=operator_headers,
                          json={"status": "IN_PROGRESS"})

    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(pool.map(update, range(10)))
    assert all(r.status_code == 200 and r.json()["status"] == "IN_PROGRESS" for r in responses)
    rows = notifications(session_factory, issue_id)
    assert len(rows) == 1 and rows[0].status == "SENT"


@pytest.mark.parametrize("conflict", [False, True])
def test_parallel_idempotent_create(client, user_headers, session_factory, conflict):
    barrier = Barrier(2)
    headers = user_headers | {"X-Idempotency-Key": "parallel-create"}

    def create(index):
        barrier.wait(timeout=10)
        return client.post("/issues", headers=headers, json=payload(
            title=f"Заявка номер {index if conflict else 0}"
        ))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, range(2)))
    assert sorted(r.status_code for r in responses) == ([201, 409] if conflict else [200, 201])
    with session_factory() as session:
        rows = list(session.scalars(select(Issue).where(Issue.request_key == "parallel-create")))
        assert len(rows) == 1
    if not conflict:
        assert responses[0].json()["id"] == responses[1].json()["id"]


def test_seed_contract_and_preservation(db_engine, session_factory):
    with session_factory() as session:
        issue = session.get(Issue, "90000000-0000-0000-0000-000000000001")
        issue.title = "Изменённая демонстрационная заявка"
        session.commit()
    init_database()
    init_database()
    assert set(inspect(db_engine).get_table_names()) == {"utility_issues", "notification_notifications"}
    with session_factory() as session:
        assert session.get(Issue, issue.id).title == "Изменённая демонстрационная заявка"
        demo = session.get(Notification, "80000000-0000-0000-0000-000000000001")
        assert demo.channel == "PUSH" and demo.user_id == demo.recipient == issue.user_id
        assert demo.status == "SENT" and demo.sent_at is not None


def test_issue_commit_failure_is_not_swallowed(
    client, user_headers, operator_headers, session_factory, monkeypatch
):
    issue_id = client.post("/issues", headers=user_headers, json=payload()).json()["id"]
    calls = []

    class Spy:
        def send(self, **kwargs):
            calls.append(kwargs)

    client.app.dependency_overrides[get_notification_api] = Spy
    def fail_commit(self):
        raise SQLAlchemyError("issue commit failed")
    monkeypatch.setattr(session_factory.class_, "commit", fail_commit)
    with pytest.raises(SQLAlchemyError, match="issue commit failed"):
        client.put(f"/issues/{issue_id}", headers=operator_headers, json={"status": "IN_PROGRESS"})
    assert calls == []
    with session_factory() as session:
        assert session.get(Issue, issue_id).status == "NEW"


@pytest.mark.parametrize("role", ["OPERATOR", "ADMIN"])
def test_operator_and_admin_can_update(client, user_headers, token_for, role):
    issue_id = client.post("/issues", headers=user_headers, json=payload()).json()["id"]
    assert client.put(f"/issues/{issue_id}", headers={"Authorization": f"Bearer {token_for(role)}"},
                      json={"status": "RESOLVED"}).status_code == 200


def test_idempotency_is_scoped_to_user_and_normalized_payload(client, user_headers, token_for):
    headers = user_headers | {"X-Idempotency-Key": "shared-key"}
    first = client.post("/issues", headers=headers, json=payload())
    replay = client.post("/issues", headers=headers,
                         json=payload(category="LIGHTING", address="Улица Мира, 10"))
    assert first.status_code == 201 and replay.status_code == 200
    other = client.post("/issues", headers={"Authorization": f"Bearer {token_for(user_id=str(uuid4()))}",
                                            "X-Idempotency-Key": "shared-key"}, json=payload())
    assert other.status_code == 201 and other.json()["id"] != first.json()["id"]
    ids = [client.post("/issues", headers=user_headers, json=payload()).json()["id"] for _ in range(2)]
    assert ids[0] != ids[1]
