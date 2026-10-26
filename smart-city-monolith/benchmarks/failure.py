"""Проверка отказа и восстановления выбранной пары на новых заявках."""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx

from run import Stand, command, token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("micro", "mono"), required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--notification-url", required=True)
    parser.add_argument("--compose", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--phase", choices=("failure", "recovery"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--docker-command", nargs="+", default=["docker"])
    args = parser.parse_args()
    stand = Stand(args)
    secret = os.environ.get("JWT_SECRET", "development-jwt-secret")
    service_token = os.environ.get("SERVICE_TOKEN", "development-service-token")
    data = {"version": args.version, "user_id": str(uuid4())} if args.phase == "failure" else json.loads(args.output.read_text(encoding="utf-8"))
    user_id = data["user_id"]
    user_headers = {"Authorization": "Bearer " + token(secret, user_id, "USER")}
    operator_headers = {"Authorization": "Bearer " + token(secret, user_id, "OPERATOR")}
    with httpx.Client(base_url=args.url, timeout=30, trust_env=False) as client:
        def create_and_change():
            created = client.post("/issues", headers=user_headers, json={
                "title": "Эксперимент с отказом", "description": "Проверка сохранения заявки",
                "category": "LIGHTING", "address": "Тестовая улица, 10"})
            assert created.status_code == 201
            issue_id = created.json()["id"]
            changed = client.put(f"/issues/{issue_id}", headers=operator_headers, json={"status": "IN_PROGRESS"})
            assert changed.status_code == 200 and changed.json()["status"] == "IN_PROGRESS"
            saved = next(row for row in stand.rows("issues", user_id) if row["id"] == issue_id)
            assert saved["status"] == "IN_PROGRESS"
            notifications = [row for row in stand.rows("notifications", user_id)
                             if row["message"] == f"Заявка {issue_id} получила статус IN_PROGRESS"]
            assert len(notifications) == 1
            row = notifications[0]
            return {"http_status": changed.status_code, "response": changed.json(),
                    "saved_issue_status": saved["status"], "notification_status": row["status"],
                    "sent_at": row["sent_at"]}

        if args.phase == "failure":
            direct = client.post(args.notification_url + "/notifications", headers={"X-Service-Token": service_token},
                                 json={"user_id": user_id, "recipient": user_id, "channel": "PUSH", "message": "Прямой HTTP при отказе"})
            assert direct.status_code == 500
            data["direct_notification_http_status"] = direct.status_code
            data["failure"] = create_and_change()
            assert data["failure"]["notification_status"] == "PENDING" and data["failure"]["sent_at"] is None
            direct_rows = [row for row in stand.rows("notifications", user_id) if row["message"] == "Прямой HTTP при отказе"]
            assert len(direct_rows) == 1 and direct_rows[0]["status"] == "PENDING" and direct_rows[0]["sent_at"] is None
            logs = command(stand.docker + ["logs", stand.containers[-1]])
            data["notification_http_500_observed"] = '500 Internal Server Error' in logs
            assert data["notification_http_500_observed"]
        else:
            failed_id = data["failure"]["response"]["id"]
            before = len(stand.rows("notifications", user_id))
            replay = client.put(f"/issues/{failed_id}", headers=operator_headers, json={"status": "IN_PROGRESS"})
            assert replay.status_code == 200 and len(stand.rows("notifications", user_id)) == before
            data["same_status_does_not_retry"] = True
            data["recovery"] = create_and_change()
            assert data["recovery"]["notification_status"] == "SENT" and data["recovery"]["sent_at"] is not None
            previous = [row for row in stand.rows("notifications", user_id)
                        if row["message"] == f"Заявка {failed_id} получила статус IN_PROGRESS"]
            assert len(previous) == 1 and previous[0]["status"] == "PENDING" and previous[0]["sent_at"] is None
            data["previous_pending_preserved"] = True
            data["passed"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"version": args.version, "phase": args.phase, "passed": True}), flush=True)


if __name__ == "__main__":
    main()
