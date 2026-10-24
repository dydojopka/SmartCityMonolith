from hashlib import sha256
from hmac import compare_digest

from fastapi import Header, HTTPException, status


def verify_sensor_key(
    x_sensor_key: str | None = Header(default=None, alias="X-Sensor-Key"),
) -> str:
    if not x_sensor_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный ключ датчика",
        )
    return x_sensor_key


def hash_sensor_key(key: str) -> str:
    return sha256(key.encode()).hexdigest()


def sensor_key_matches(key: str, digest: str) -> bool:
    return compare_digest(hash_sensor_key(key), digest)
