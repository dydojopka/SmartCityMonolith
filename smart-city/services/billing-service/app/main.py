import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hmac import compare_digest
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.errors import validation_error
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import get_db, init_database
from app.demo_provider import confirm_demo_payment
from app.models import Invoice, Payment, WebhookEvent
from app.invariants import validate_invoice, validate_payment
from app.notifications import notify_payment_success
from app.schemas import (
    InvoiceResponse,
    PaymentCreateRequest,
    PaymentResponse,
    PaymentWebhookRequest,
)
from app.seed import seed_database

SERVICE_NAME = os.getenv("SERVICE_NAME", "billing-service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVICE_NAME)


def begin_write(db: Session) -> None:
    # Serialize SQLite writers before the reads as well as the writes.
    # UNIQUE constraints remain the final defense against duplicate payments.
    if db.get_bind().dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")


def checked_invoice(invoice):
    try:
        validate_invoice(invoice)
    except ValueError:
        raise HTTPException(409, "Данные счёта требуют сверки") from None


def checked_payment(db, payment):
    if payment is None:
        raise HTTPException(409, "Событие не связано с платежом")
    invoice = db.get(Invoice, payment.invoice_id)
    if invoice is None:
        raise HTTPException(409, "Платёж не связан со счётом")
    try:
        validate_payment(payment, invoice)
    except ValueError:
        raise HTTPException(409, "Данные платежа требуют сверки") from None
    return payment


def checked_event(db, event):
    payload = event.payload
    if event.event_type != "PAYMENT_SUCCESS" or not isinstance(payload, dict) or payload.get("payment_id") != event.payment_id:
        raise HTTPException(409, "Данные события требуют сверки")
    if payload.get("external_event_id", event.external_event_id) != event.external_event_id:
        raise HTTPException(409, "Данные события требуют сверки")
    payment = checked_payment(db, db.get(Payment, event.payment_id))
    if payment.status != "SUCCEEDED":
        raise HTTPException(409, "Событие не подтверждает успешный платёж")
    return payment


def replay_payment(db, existing, payload, user, response):
    if existing.user_id != user.id:
        raise HTTPException(403, "Недостаточно прав")
    if existing.invoice_id != str(payload.invoice_id):
        raise HTTPException(409, "Ключ уже использован для другого счёта")
    response.status_code = 200
    logger.info("payment_replayed payment_id=%s", existing.id)
    return checked_payment(db, existing)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    from app.database import SessionLocal

    with SessionLocal() as session:
        seed_database(session)
    logger.info("%s started", SERVICE_NAME)
    yield


app = FastAPI(title="Billing Service", lifespan=lifespan)
app.add_exception_handler(RequestValidationError, validation_error)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/accounts/{user_id}/invoices", response_model=list[InvoiceResponse])
def list_user_invoices(
    user_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Invoice]:
    if current_user.id != user_id and current_user.role != "ADMIN":
        logger.warning(
            "invoices_access_denied requested_user_id=%s current_user_id=%s",
            user_id,
            current_user.id,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    invoices = list(
        db.scalars(
            select(Invoice)
            .where(Invoice.user_id == user_id)
            .order_by(Invoice.created_at.desc())
        ).all()
    )
    for invoice in invoices:
        checked_invoice(invoice)
    return invoices


@app.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreateRequest,
    response: Response,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Payment:
    begin_write(db)
    existing = db.scalar(
        select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
    )
    if existing is not None:
        return replay_payment(db, existing, payload, current_user, response)

    invoice = db.get(Invoice, str(payload.invoice_id))
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Счёт не найден")

    if invoice.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    checked_invoice(invoice)

    if invoice.status != "PENDING" or db.scalar(select(Payment.id).where(Payment.invoice_id == invoice.id, Payment.status.in_(["CREATED", "SUCCEEDED"]))) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Счёт не ожидает оплаты"
        )

    payment = Payment(
        id=str(uuid4()),
        invoice_id=invoice.id,
        user_id=current_user.id,
        amount_cents=invoice.amount_cents,
        status="CREATED",
        idempotency_key=payload.idempotency_key,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
        )
        if existing is not None:
            return replay_payment(db, existing, payload, current_user, response)
        if db.scalar(select(Payment.id).where(Payment.invoice_id == invoice.id, Payment.status.in_(["CREATED", "SUCCEEDED"]))) is not None:
            raise HTTPException(409, "Платёж для счёта уже существует") from None
        raise

    db.refresh(payment)
    logger.info(
        "payment_created payment_id=%s invoice_id=%s user_id=%s amount_cents=%s",
        payment.id,
        invoice.id,
        current_user.id,
        payment.amount_cents,
    )
    return payment


@app.post("/payments/{payment_id}/demo-success", response_model=PaymentResponse)
def demo_payment_success(
    payment_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Payment:
    if os.getenv("DEMO_PAYMENTS_ENABLED", "false").lower() != "true":
        raise HTTPException(404, "Демо-оплата отключена")

    payment = db.get(Payment, str(payment_id))
    if payment is None:
        raise HTTPException(404, "Платёж не найден")
    if payment.user_id != current_user.id:
        raise HTTPException(403, "Недостаточно прав")
    checked_payment(db, payment)
    if payment.status == "SUCCEEDED":
        return payment
    if payment.status != "CREATED":
        raise HTTPException(409, "Платёж не ожидает оплаты")

    # End our read transaction before the HTTP callback writes to the same DB.
    # Only the existing webhook may commit the financial state transition.
    db.rollback()
    confirm_demo_payment(str(payment_id))
    payment = checked_payment(db, db.get(Payment, str(payment_id)))
    if payment.status != "SUCCEEDED":
        raise HTTPException(502, "Демо-оплата ещё не подтверждена. Повторите оплату.")
    return payment


@app.post("/payments/webhook/success", response_model=PaymentResponse)
def payment_webhook_success(
    payload: PaymentWebhookRequest,
    db: Annotated[Session, Depends(get_db)],
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> Payment:
    expected = os.getenv("SERVICE_TOKEN", "development-service-token")
    if not x_service_token or not compare_digest(x_service_token.encode(), expected.encode()):
        logger.warning("webhook_invalid_service_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный служебный токен")

    begin_write(db)
    existing_event = db.scalar(
        select(WebhookEvent).where(WebhookEvent.external_event_id == payload.external_event_id)
    )
    if existing_event is not None:
        if existing_event.payment_id != str(payload.payment_id):
            raise HTTPException(409, "Событие относится к другому платежу")
        return checked_event(db, existing_event)

    payment = db.get(Payment, str(payload.payment_id))
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платёж не найден")

    invoice = db.get(Invoice, payment.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Счёт не найден")

    checked_payment(db, payment)

    changed = payment.status != "SUCCEEDED"
    if changed:
        if payment.status != "CREATED" or invoice.status != "PENDING":
            raise HTTPException(409, "Счёт или платёж не ожидает оплаты")
        now = datetime.now(timezone.utc)
        result = db.execute(update(Invoice).where(Invoice.id == invoice.id, Invoice.status == "PENDING").values(status="PAID", paid_at=now))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Счёт уже обработан")
        result = db.execute(update(Payment).where(Payment.id == payment.id, Payment.status == "CREATED").values(status="SUCCEEDED", external_event_id=payload.external_event_id))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Платёж уже обработан")
    db.add(
        WebhookEvent(
            id=str(uuid4()),
            external_event_id=payload.external_event_id,
            payment_id=payment.id,
            payload=payload.model_dump(mode="json"),
        )
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        event = db.scalar(select(WebhookEvent).where(WebhookEvent.external_event_id == payload.external_event_id))
        if event is not None:
            if event.payment_id != str(payload.payment_id):
                raise HTTPException(409, "Событие относится к другому платежу") from None
            return checked_event(db, event)
        raise

    db.refresh(payment)
    if changed:
        logger.info(
            "payment_success payment_id=%s invoice_id=%s user_id=%s",
            payment.id,
            invoice.id,
            payment.user_id,
        )
        notify_payment_success(
            payment_id=payment.id,
            user_id=payment.user_id,
            invoice_id=invoice.id,
            amount_cents=payment.amount_cents,
        )
    return payment
