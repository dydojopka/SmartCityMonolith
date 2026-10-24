import logging
import os

import httpx

logger = logging.getLogger(os.getenv("SERVICE_NAME", "utility-service"))


def notify_issue_status_changed(issue_id: str, user_id: str, issue_status: str) -> None:
    """Best-effort notification; the already committed issue must remain intact."""
    try:
        response = httpx.post(
            f"{os.getenv('NOTIFICATION_URL', 'http://notification-service:8000')}/notifications",
            headers={"X-Service-Token": os.getenv("SERVICE_TOKEN", "development-service-token")},
            json={
                "user_id": user_id,
                "channel": "PUSH",
                "recipient": user_id,
                "subject": "Статус заявки изменён",
                "message": f"Заявка {issue_id} получила статус {issue_status}",
            },
            timeout=3.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("notification_failed issue_id=%s user_id=%s", issue_id, user_id)
