import logging
import os

import httpx

logger = logging.getLogger(os.getenv("SERVICE_NAME", "transport-service"))


def notify_parking_reserved(
    reservation_id: str, user_id: str, parking_name: str
) -> None:
    """Best-effort notification; the already committed reservation must remain intact."""
    try:
        response = httpx.post(
            f"{os.getenv('NOTIFICATION_URL', 'http://notification-service:8000')}/notifications",
            headers={"X-Service-Token": os.getenv("SERVICE_TOKEN", "development-service-token")},
            json={
                "user_id": user_id,
                "channel": "PUSH",
                "recipient": user_id,
                "subject": "Парковка забронирована",
                "message": f"Место на парковке {parking_name} забронировано",
            },
            timeout=3.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception(
            "notification_failed reservation_id=%s user_id=%s",
            reservation_id,
            user_id,
        )
