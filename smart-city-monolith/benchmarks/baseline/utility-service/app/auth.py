import os
from uuid import UUID
from dataclasses import dataclass
from typing import Annotated, Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    role: str


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
