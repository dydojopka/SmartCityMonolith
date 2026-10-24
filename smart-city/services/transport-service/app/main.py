import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.errors import validation_error
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, get_current_user
from app.database import get_db, init_database
from app.models import Parking, Reservation, Vehicle
from app.notifications import notify_parking_reserved
from app.schemas import (
    ParkingResponse,
    ReservationResponse,
    VehicleResponse,
)
from app.seed import seed_database

SERVICE_NAME = os.getenv("SERVICE_NAME", "transport-service")
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


app = FastAPI(title="Transport Service", lifespan=lifespan)
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


@app.get("/vehicles", response_model=list[VehicleResponse])
def list_vehicles(db: Annotated[Session, Depends(get_db)]) -> list[Vehicle]:
    return list(db.scalars(select(Vehicle).order_by(Vehicle.id)).all())


@app.get("/parking", response_model=list[ParkingResponse])
def list_parking(db: Annotated[Session, Depends(get_db)]) -> list[Parking]:
    return list(db.scalars(select(Parking).order_by(Parking.name)).all())


@app.post(
    "/parking/{parking_id}/reserve",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def reserve_parking(
    parking_id: UUID,
    response: Response,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    request_key: Annotated[str | None, Header(alias="X-Idempotency-Key", min_length=1, max_length=128)] = None,
) -> Reservation:
    parking_id = str(parking_id)
    # Serialize SQLite writers before looking up a replay, including the last place.
    if db.get_bind().dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    def replay():
        existing = db.scalar(select(Reservation).where(Reservation.user_id == current_user.id, Reservation.request_key == request_key))
        if existing is not None:
            if existing.parking_id != parking_id:
                raise HTTPException(409, "Ключ уже использован для другой парковки")
            response.status_code = 200
        return existing
    if request_key is not None:
        existing = replay()
        if existing is not None:
            return existing
    parking = db.get(Parking, parking_id)
    if parking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Парковка не найдена")

    result = db.execute(
        update(Parking)
        .where(Parking.id == parking_id, Parking.available_spaces > 0)
        .values(available_spaces=Parking.available_spaces - 1)
    )
    if result.rowcount == 0:
        db.rollback()
        logger.info("parking_reserve_rejected parking_id=%s user_id=%s", parking_id, current_user.id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Нет свободных мест")

    reservation = Reservation(
        id=str(uuid4()),
        parking_id=parking_id,
        user_id=current_user.id,
        request_key=request_key,
        status="ACTIVE",
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # The decrement must roll back together with a losing insert.
        if request_key is not None:
            existing = replay()
            if existing is not None:
                return existing
        raise
    db.refresh(reservation)

    logger.info(
        "parking_reserved reservation_id=%s parking_id=%s user_id=%s",
        reservation.id,
        parking_id,
        current_user.id,
    )

    notify_parking_reserved(
        reservation_id=reservation.id,
        user_id=current_user.id,
        parking_name=parking.name,
    )

    return reservation
