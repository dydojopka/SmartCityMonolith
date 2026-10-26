import logging

logger = logging.getLogger("smart-city-monolith.utility")


def notify_issue_status_changed(
    notification_api,
    issue_id: str,
    user_id: str,
    issue_status: str,
) -> None:
    """Best-effort notification; the already committed issue must remain intact."""
    try:
        notification_api.send(
            user_id=user_id,
            channel="PUSH",
            recipient=user_id,
            subject="Статус заявки изменён",
            message=f"Заявка {issue_id} получила статус {issue_status}",
        )
    except Exception:
        # Любая ошибка фасада (включая RuntimeError при NOTIFICATION_FAIL_SEND)
        # логируется, но НЕ пробрасывается — заявка уже сохранена.
        logger.exception(
            "notification_failed issue_id=%s user_id=%s", issue_id, user_id
        )
