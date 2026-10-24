import logging
import os

import httpx

logger = logging.getLogger(os.getenv("SERVICE_NAME", "billing-service"))


def notify_payment_success(
    payment_id: str, user_id: str, invoice_id: str, amount_cents: int
) -> None:
    """Best-effort notification; the already committed payment must remain intact."""
    try:
        response = httpx.post(
            f"{os.getenv('NOTIFICATION_URL', 'http://notification-service:8000')}/notifications",
            headers={"X-Service-Token": os.getenv("SERVICE_TOKEN", "development-service-token")},
            json={
                "user_id": user_id,
                "channel": "PUSH",
                "recipient": user_id,
                "subject": "Платёж проведён",
                "message": f"Счёт {invoice_id} оплачен на {amount_cents / 100:.2f} ₽",
            },
            timeout=3.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception(
            "notification_failed payment_id=%s user_id=%s",
            payment_id,
            user_id,
        )