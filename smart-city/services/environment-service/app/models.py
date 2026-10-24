from datetime import datetime, timezone

from uuid import uuid4
from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime


class Sensor(Base):
    __tablename__ = "sensors"
    __table_args__ = (CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_sensor_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(100))
    # Keep historical descriptions during migration; the public contract uses coordinates.
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str] = mapped_column(String(50))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    api_key_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )

    readings: Mapped[list["SensorReading"]] = relationship(
        back_populates="sensor", cascade="all, delete-orphan"
    )


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (Index("ix_sensor_readings_sensor_id_measured_at", "sensor_id", "measured_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sensor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sensors.id", ondelete="CASCADE")
    )
    value: Mapped[float] = mapped_column(Float)
    # Historical readings may have supplied their own unit; do not discard it.
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    measured_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )
    received_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc)
    )

    sensor: Mapped[Sensor] = relationship(back_populates="readings")
