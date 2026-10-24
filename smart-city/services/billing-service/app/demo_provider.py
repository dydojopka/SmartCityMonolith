"""Server-side payment simulation; the service token never reaches the browser."""
import logging
import os

import httpx
from fastapi import HTTPException

logger = logging.getLogger(os.getenv("SERVICE_NAME", "billing-service"))


def confirm_demo_payment(payment_id: str) -> None:
    # Stable event ID makes retries after a lost callback response safe.
    payload = {
        "payment_id": payment_id,
        "external_event_id": f"demo-payment-{payment_id}",
    }
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            response = client.post(
                os.getenv("BILLING_WEBHOOK_URL", "http://127.0.0.1:8000/payments/webhook/success"),
                headers={"X-Service-Token": os.getenv("SERVICE_TOKEN", "development-service-token")},
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError:
        # Do not log request headers or exception details containing credentials.
        logger.warning("demo_confirmation_failed payment_id=%s", payment_id)
        raise HTTPException(502, "Не удалось подтвердить демо-оплату. Повторите оплату: новый платёж не будет создан.") from None
