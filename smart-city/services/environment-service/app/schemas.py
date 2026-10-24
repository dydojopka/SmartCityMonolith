from datetime import datetime, timezone
from uuid import UUID
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

SensorStatus = Literal["ACTIVE", "INACTIVE"]


class SensorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: str
    unit: str
    latitude: float
    longitude: float
    status: SensorStatus
    last_seen_at: datetime | None
    created_at: datetime


class SensorReadingCreate(BaseModel):
    sensor_id: UUID
    value: float = Field(allow_inf_nan=False)
    measured_at: AwareDatetime

    @field_validator("measured_at")
    @classmethod
    def normalize_time(cls, value):
        try:
            return value.astimezone(timezone.utc)
        except OverflowError:
            raise ValueError("Дата вне допустимого диапазона UTC") from None


class SensorReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sensor_id: UUID
    value: float
    measured_at: datetime
    received_at: datetime
