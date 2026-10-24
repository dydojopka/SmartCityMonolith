from app import database


def init_database() -> None:
    # После принятия модулей здесь регистрируются обе models до create_all.
    database.Base.metadata.create_all(bind=database.engine)
    # Здесь будут вызваны seed_database(session) обоих модулей в отдельных сессиях.
    # Пока моделей и seed нет, создаётся только SQLite-файл, без фиктивных данных.


if __name__ == "__main__":
    init_database()
