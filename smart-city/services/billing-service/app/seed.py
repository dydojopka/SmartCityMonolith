from datetime import date
from sqlalchemy.orm import Session

from app.models import Invoice

# UUID совпадают с identity-service/app/seed.py
USER_IVAN = "00000000-0000-0000-0000-000000000001"   # USER
USER_ANNA = "00000000-0000-0000-0000-000000000002"   # OPERATOR
USER_PAVEL = "00000000-0000-0000-0000-000000000003"  # ADMIN

DEMO_INVOICES = (
    {
        "id": "50000000-0000-0000-0000-000000000001",
        "user_id": USER_IVAN,
        "amount_cents": 150000,
        "status": "PENDING",
        "description": "Коммунальные услуги за месяц",
    },
    {
        "id": "50000000-0000-0000-0000-000000000002",
        "user_id": USER_IVAN,
        "amount_cents": 50000,
        "status": "PENDING",
        "description": "Парковочный абонемент",
    },
    {
        "id": "50000000-0000-0000-0000-000000000003",
        "user_id": USER_ANNA,
        "amount_cents": 99000,
        "status": "PENDING",
        "description": "Электроэнергия",
    },
    {
        "id": "50000000-0000-0000-0000-000000000004",
        "user_id": USER_PAVEL,
        "amount_cents": 250000,
        "status": "PENDING",
        "description": "Аренда офиса",
    },
)


def seed_database(session: Session) -> None:
    for invoice in DEMO_INVOICES:
        if session.get(Invoice, invoice["id"]) is None:
            session.add(Invoice(**invoice, due_date=date(2026, 10, 10)))
    session.commit()
