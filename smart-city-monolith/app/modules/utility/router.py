# Заготовка переноса, не реализация модуля. Владелец: daNYA.
# Источник: https://github.com/dydojopka/SmartCity @ 6983e58de588795731a548e31534794873835057
# Файл: smart-city/services/utility-service/app/main.py
# Задание: docs/tasks/daNYA.md (от корня репозитория).
# Перед включением: оставить три бизнес-маршрута на APIRouter без префикса;
# не переносить FastAPI, lifespan, CORS, /health и общую настройку приложения.
# Исправить импорты на свой модуль. Фасад получать через get_notification_api/Depends
# и передавать helper уведомлений только после условного UPDATE, commit и refresh.
# Сохранить роли, replay/conflict POST и защиту от конкурентных POST/PUT.
#
import logging
from typing import TYPE_CHECKING, Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user, require_roles
from app.database import get_db
from app.dependencies import get_notification_api
from app.modules.utility.models import Issue
from app.modules.utility.notifications import notify_issue_status_changed
from app.modules.utility.schemas import (
    IssueCreate,
    IssueResponse,
    IssueStatusUpdate,
)

if TYPE_CHECKING:
    from app.modules.notification.api import NotificationApi

logger = logging.getLogger("smart-city-monolith.utility")

router = APIRouter()


@router.post(
    "/issues",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_issue(
    payload: IssueCreate,
    response: Response,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    request_key: Annotated[
        str | None,
        Header(alias="X-Idempotency-Key", min_length=1, max_length=128),
    ] = None,
) -> Issue:
    def replay():
        existing = db.scalar(
            select(Issue).where(
                Issue.user_id == current_user.id,
                Issue.request_key == request_key,
            )
        )
        if existing is not None:
            if any(
                getattr(existing, key) != value
                for key, value in payload.model_dump().items()
            ):
                raise HTTPException(409, "Ключ уже использован для другой заявки")
            response.status_code = 200
        return existing

    if request_key is not None:
        existing = replay()
        if existing is not None:
            return existing

    issue = Issue(
        id=str(uuid4()),
        user_id=current_user.id,
        request_key=request_key,
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=payload.category.strip().upper(),
        address=payload.address.strip(),
        status="NEW",
    )
    db.add(issue)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if request_key is not None:
            existing = replay()
            if existing is not None:
                return existing
        raise
    db.refresh(issue)
    logger.info("issue_created issue_id=%s user_id=%s", issue.id, current_user.id)
    return issue


@router.get("/issues", response_model=list[IssueResponse])
def list_issues(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Issue]:
    query = select(Issue).order_by(Issue.created_at.desc())
    if current_user.role not in {"OPERATOR", "ADMIN"}:
        query = query.where(Issue.user_id == current_user.id)
    return list(db.scalars(query).all())


@router.put("/issues/{issue_id}", response_model=IssueResponse)
def update_issue_status(
    issue_id: str,
    payload: IssueStatusUpdate,
    _: Annotated[CurrentUser, Depends(require_roles("OPERATOR", "ADMIN"))],
    db: Annotated[Session, Depends(get_db)],
    # Any + TYPE_CHECKING: роутер импортируется, даже если Иванов NotificationApi
    # ещё не готов. При запросе Depends(get_notification_api) импортирует реальный
    # фасад (ленивый импорт внутри app/dependencies.py).
    notification_api: Annotated[Any, Depends(get_notification_api)],
) -> Issue:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена"
        )

    result = db.execute(
        update(Issue)
        .where(Issue.id == issue.id, Issue.status != payload.status)
        .values(status=payload.status)
    )
    db.commit()

    if result.rowcount:
        logger.info(
            "issue_status_updated issue_id=%s status=%s", issue.id, payload.status
        )
        # Важно: notify ДО db.refresh().
        # db.refresh() открывает SHARED-транзакцию SQLite и заблокировал бы
        # писателя внутри NotificationApi (его собственная сессия).
        # После db.commit() активной транзакции нет — конфликта нет.
        notify_issue_status_changed(
            notification_api, issue.id, issue.user_id, payload.status
        )

    db.refresh(issue)
    return issue