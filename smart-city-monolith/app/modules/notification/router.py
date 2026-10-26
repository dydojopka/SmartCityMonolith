from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import get_notification_api
from app.modules.notification.api import NotificationApi
from app.modules.notification.schemas import NotificationCreate, NotificationResponse
from app.modules.notification.security import verify_service_token

router = APIRouter()


@router.post(
    "/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notification(
    payload: NotificationCreate,
    _: Annotated[None, Depends(verify_service_token)],
    api: Annotated[NotificationApi, Depends(get_notification_api)],
) -> NotificationResponse:
    return api.send(
        user_id=str(payload.user_id) if payload.user_id is not None else None,
        channel=payload.channel,
        recipient=payload.recipient,
        subject=payload.subject,
        message=payload.message,
    )