import os
from hmac import compare_digest

from fastapi import Header, HTTPException, status


def verify_service_token(
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
) -> None:
    expected = os.getenv("SERVICE_TOKEN", "development-service-token")
    if not x_service_token or not compare_digest(x_service_token.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный служебный токен",
        )
