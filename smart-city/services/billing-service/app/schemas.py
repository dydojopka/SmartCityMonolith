from datetime import date, datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InvoiceStatus = Literal["PENDING", "PAID", "CANCELLED"]
PaymentStatus = Literal["CREATED", "SUCCEEDED", "FAILED"]


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    amount_cents: int
    status: InvoiceStatus
    description: str | None
    due_date: date | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaymentCreateRequest(BaseModel):
    invoice_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=128)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_id: str
    user_id: str
    amount_cents: int
    status: PaymentStatus
    idempotency_key: str
    external_event_id: str | None
    created_at: datetime
    updated_at: datetime


class PaymentWebhookRequest(BaseModel):
    external_event_id: str = Field(min_length=1, max_length=128)
    payment_id: UUID
