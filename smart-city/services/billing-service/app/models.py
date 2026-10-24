from datetime import date, datetime, timezone
from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (CheckConstraint("typeof(amount_cents) = 'integer' AND amount_cents > 0", name="ck_invoice_amount"), CheckConstraint("status IN ('PENDING','PAID','CANCELLED')", name="ck_invoice_status"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("typeof(amount_cents) = 'integer' AND amount_cents > 0", name="ck_payment_amount"),
        CheckConstraint("status IN ('CREATED','SUCCEEDED','FAILED')", name="ck_payment_status"),
        Index("uq_active_payment_invoice", "invoice_id", unique=True, sqlite_where=text("status IN ('CREATED','SUCCEEDED')")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invoices.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="CREATED", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    external_event_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    payment_id: Mapped[str] = mapped_column(String(36), ForeignKey("payments.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), default="PAYMENT_SUCCESS")
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
