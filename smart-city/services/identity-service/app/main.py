import logging
import os
from contextlib import asynccontextmanager

from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.errors import validation_error
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db, init_database
from app.models import User
from app.schemas import LoginRequest, PublicUserResponse, RegisterRequest, TokenResponse, UserResponse
from app.seed import seed_database

SERVICE_NAME = os.getenv("SERVICE_NAME", "identity-service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVICE_NAME)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    from app.database import SessionLocal

    with SessionLocal() as session:
        seed_database(session)
    logger.info("%s started", SERVICE_NAME)
    yield


app = FastAPI(title="Identity Service", lifespan=lifespan)
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


@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> User:
    user = User(
        id=str(uuid4()),
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        role="USER",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email уже зарегистрирован") from None
    db.refresh(user)
    logger.info("user_registered user_id=%s", user.id)
    return user


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        logger.warning("login_failed email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")

    logger.info("user_logged_in user_id=%s", user.id)
    return TokenResponse(access_token=create_access_token(user.id, user.role))


@app.get("/users/me", response_model=UserResponse)
def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = db.get(User, current_user.id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь недоступен")
    return user


@app.get("/users/{user_id}", response_model=PublicUserResponse)
def get_user(user_id: str, db: Annotated[Session, Depends(get_db)]) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user


@app.get("/users", response_model=list[PublicUserResponse])
def list_users(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[User]:
    return list(db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.created_at)).all())
