from sqlalchemy.orm import Session

from app.models import Parking, Vehicle

DEMO_VEHICLES = (
    {
        "id": "10000000-0000-0000-0000-000000000001",
        "type": "BUS",
        "route_number": "24",
        "latitude": 55.7558,
        "longitude": 37.6173,
        "status": "ACTIVE",
    },
    {
        "id": "10000000-0000-0000-0000-000000000002",
        "type": "TRAM",
        "route_number": "7",
        "latitude": 55.7601,
        "longitude": 37.6200,
        "status": "ACTIVE",
    },
    {
        "id": "10000000-0000-0000-0000-000000000003",
        "type": "BUS",
        "route_number": "12",
        "latitude": 55.7500,
        "longitude": 37.6100,
        "status": "ACTIVE",
    },
)

DEMO_PARKINGS = (
    {
        "id": "20000000-0000-0000-0000-000000000001",
        "name": "Центральная парковка",
        "address": "ул. Тверская, 1",
        "latitude": 55.7570,
        "longitude": 37.6150,
        "total_spaces": 10,
        "available_spaces": 10,
        "price_per_hour_cents": 20000,
    },
    {
        "id": "20000000-0000-0000-0000-000000000002",
        "name": "Парковка у парка",
        "address": "ул. Парковая, 10",
        "latitude": 55.7300,
        "longitude": 37.6000,
        "total_spaces": 5,
        "available_spaces": 5,
        "price_per_hour_cents": 15000,
    },
)


def seed_database(session: Session) -> None:
    for vehicle in DEMO_VEHICLES:
        if session.get(Vehicle, vehicle["id"]) is None:
            session.add(Vehicle(**vehicle))

    for parking in DEMO_PARKINGS:
        if session.get(Parking, parking["id"]) is None:
            session.add(Parking(**parking))

    session.commit()
