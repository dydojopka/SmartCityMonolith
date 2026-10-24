import os
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    role: str


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except (UnknownHashError, ValueError):
        return False


def create_access_token(user_id: str, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
    )
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expires_at},
        os.getenv("JWT_SECRET", "development-jwt-secret"),
        algorithm="HS256",
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется JWT",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            os.getenv("JWT_SECRET", "development-jwt-secret"),
            algorithms=["HS256"],
            options={"require": ["sub", "role", "exp"]},
        )
        user_id = payload["sub"]
        role = payload["role"]
        UUID(user_id)
        if role not in {"USER", "OPERATOR", "ADMIN"}:
            raise ValueError("Invalid role")
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError, AttributeError, OverflowError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный JWT",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return CurrentUser(id=str(UUID(user_id)), role=role)


def require_roles(*allowed_roles: str) -> Callable:
    def check_role(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return current_user

    return check_role
