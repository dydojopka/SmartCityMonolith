import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models import Sensor, SensorReading
from app.security import hash_sensor_key

DEMO_SENSORS = (
    {"id": "40000000-0000-0000-0000-000000000001", "name": "Датчик температуры №1", "type": "TEMPERATURE", "unit": "°C", "latitude": 59.9343, "longitude": 30.3351},
    {"id": "40000000-0000-0000-0000-000000000002", "name": "Датчик влажности №1", "type": "HUMIDITY", "unit": "%", "latitude": 59.94, "longitude": 30.34},
)


def seed_database(session: Session) -> None:
    now = datetime.now(timezone.utc)
    digest = hash_sensor_key(os.getenv("SENSOR_API_KEY", "demo-sensor-key"))
    for n, data in enumerate(DEMO_SENSORS, 1):
        if session.get(Sensor, data["id"]) is None:
            session.add(Sensor(**data, api_key_hash=digest, last_seen_at=now))
        session.flush()
        reading_id = f"50000000-0000-0000-0000-{n:012d}"
        if session.get(SensorReading, reading_id) is None:
            session.add(SensorReading(id=reading_id, sensor_id=data["id"], value=18.7 if n == 1 else 60.0, measured_at=now, received_at=now))
    session.commit()
