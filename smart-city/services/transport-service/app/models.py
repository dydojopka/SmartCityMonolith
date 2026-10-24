from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (CheckConstraint("status IN ('ACTIVE','INACTIVE','MAINTENANCE')", name="ck_vehicle_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(30))
    route_number: Mapped[str] = mapped_column(String(30))
    plate_number: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    model: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )


class Parking(Base):
    __tablename__ = "parkings"
    __table_args__ = (
        CheckConstraint("total_spaces >= 0", name="ck_parking_total"),
        CheckConstraint("available_spaces >= 0 AND available_spaces <= total_spaces", name="ck_parking_available"),
        CheckConstraint("price_per_hour_cents >= 0", name="ck_parking_price"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    total_spaces: Mapped[int] = mapped_column(Integer)
    available_spaces: Mapped[int] = mapped_column(Integer, index=True)
    price_per_hour_cents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','CANCELLED','EXPIRED')", name="ck_reservation_status"),
        Index("uq_reservation_user_request", "user_id", "request_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parking_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("parkings.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    request_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
