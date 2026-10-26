from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.notification.models import Notification

DEMO_NOTIFICATION_ID = "a0000000-0000-0000-0000-000000000001"


def seed_database(session: Session) -> None:
    if session.get(Notification, DEMO_NOTIFICATION_ID) is not None:
        return

    now = datetime.now(timezone.utc)
    session.add(
        Notification(
            id=DEMO_NOTIFICATION_ID,
            user_id=None,
            recipient="demo@example.com",
            channel="EMAIL",
            subject="Демонстрационное уведомление",
            message="Это демонстрационное уведомление со статусом SENT",
            status="SENT",
            created_at=now,
            sent_at=now,
        )
    )
    session.commit()