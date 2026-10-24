import os
from typing import TYPE_CHECKING

from app.database import SessionLocal

if TYPE_CHECKING:
    from app.modules.notification.api import NotificationApi


def get_notification_api() -> "NotificationApi":
    # Импорт откладывается до обращения: фасад реализуется в модуле Notification.
    from app.modules.notification.api import NotificationApi

    return NotificationApi(
        SessionLocal,
        fail_sending=os.getenv("NOTIFICATION_FAIL_SEND", "false").strip().lower() in {"true", "1"},
    )
