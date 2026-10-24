from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import User

DEMO_PASSWORD = "demo12345"
DEMO_USERS = (
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "user@smartcity.local",
        "first_name": "Иван",
        "last_name": "Петров",
        "role": "USER",
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "email": "operator@smartcity.local",
        "first_name": "Анна",
        "last_name": "Смирнова",
        "role": "OPERATOR",
    },
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "email": "admin@smartcity.local",
        "first_name": "Павел",
        "last_name": "Волков",
        "role": "ADMIN",
    },
)


def seed_database(session: Session) -> None:
    for user_data in DEMO_USERS:
        if session.get(User, user_data["id"]) is not None:
            continue
        if session.scalar(select(User.id).where(User.email == user_data["email"])) is not None:
            raise RuntimeError("Demo email belongs to another account; resolve without replacing the account")
        session.add(User(**user_data, password_hash=hash_password(DEMO_PASSWORD)))
    session.commit()
