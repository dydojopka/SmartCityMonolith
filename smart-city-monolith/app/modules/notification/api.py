import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.modules.notification.models import Notification
from app.modules.notification.schemas import NotificationCreate, NotificationResponse

logger = logging.getLogger(__name__)


class NotificationApi:
    def __init__(self, session_factory, *, fail_sending: bool = False):
        self.session_factory = session_factory
        self.fail_sending = fail_sending

    def send(
        self,
        *,
        user_id: str | None,
        channel: str,
        recipient: str,
        subject: str | None,
        message: str,
    ) -> NotificationResponse:
        # Валидация до создания записи (даже для внутреннего вызова).
        validated = NotificationCreate(
            user_id=user_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            message=message,
        )

        with self.session_factory() as session:
            notification = Notification(
                id=str(uuid4()),
                user_id=str(validated.user_id) if validated.user_id is not None else None,
                recipient=validated.recipient,
                channel=validated.channel,
                subject=validated.subject,
                message=validated.message,
                status="PENDING",
            )
            session.add(notification)
            session.commit()
            session.refresh(notification)

            logger.info(
                "notification_pending id=%s channel=%s recipient=%s",
                notification.id,
                notification.channel,
                notification.recipient,
            )

            if self.fail_sending:
                # Исключение после commit PENDING, но до SENT.
                raise RuntimeError("Notification sending failed")

            # Имитация успешной отправки.
            notification.status = "SENT"
            notification.sent_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(notification)

            logger.info("notification_sent id=%s", notification.id)

            return NotificationResponse.model_validate(notification)