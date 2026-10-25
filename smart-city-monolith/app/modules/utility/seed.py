# Заготовка переноса, не реализация модуля. Владелец: daNYA.
# Источник: https://github.com/dydojopka/SmartCity @ 6983e58de588795731a548e31534794873835057
# Файл: smart-city/services/utility-service/app/seed.py
# Задание: docs/tasks/daNYA.md (от корня репозитория).
# Перед включением: импортировать Issue из своего модуля; сохранить фиксированный
# ID и проверку существования. Запускать только из общего init_db, не при импорте.
#
from sqlalchemy.orm import Session

from app.modules.utility.models import Issue


def seed_database(session: Session) -> None:
    if session.get(Issue, "90000000-0000-0000-0000-000000000001") is not None:
        return

    session.add(
        Issue(
            id="90000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000001",
            title="Не работает фонарь",
            description="Фонарь не включается вечером",
            category="LIGHTING",
            address="Невский проспект, 10",
            status="NEW",
        )
    )
    session.commit()