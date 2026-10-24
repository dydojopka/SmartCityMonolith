from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ReservationStatus = Literal["ACTIVE", "CANCELLED", "EXPIRED"]


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    route_number: str
    latitude: float
    longitude: float
    status: str
    updated_at: datetime


class ParkingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: str
    latitude: float
    longitude: float
    total_spaces: int
    available_spaces: int
    price_per_hour_cents: int


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    parking_id: str
    user_id: str
    status: ReservationStatus
    created_at: datetime
    expires_at: datetime | None
