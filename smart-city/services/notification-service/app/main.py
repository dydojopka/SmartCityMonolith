import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, status
from fastapi.exceptions import RequestValidationError
from app.errors import validation_error
from sqlalchemy.orm import Session

from app.database import get_db, init_database
from app.models import Notification
from app.schemas import NotificationCreate, NotificationResponse
from app.security import verify_service_token

SERVICE_NAME = os.getenv("SERVICE_NAME", "notification-service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVICE_NAME)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    logger.info("%s started", SERVICE_NAME)
    yield


app = FastAPI(title="Notification Service", lifespan=lifespan)
app.add_exception_handler(RequestValidationError, validation_error)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post(
    "/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notification(
    payload: NotificationCreate,
    _: Annotated[None, Depends(verify_service_token)],
    db: Annotated[Session, Depends(get_db)],
) -> Notification:
    notification = Notification(
        user_id=str(payload.user_id) if payload.user_id is not None else None,
        recipient=payload.recipient,
        channel=payload.channel,
        subject=payload.subject,
        message=payload.message,
        status="PENDING",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    logger.info(
        "notification_pending id=%s channel=%s recipient=%s",
        notification.id,
        notification.channel,
        notification.recipient,
    )

    # Имитация отправки. Служебный токен сюда не попадает.

    notification.status = "SENT"
    notification.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)

    logger.info("notification_sent id=%s", notification.id)
    return notification
