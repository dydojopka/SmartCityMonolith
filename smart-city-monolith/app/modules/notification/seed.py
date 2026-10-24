# Новый seed монолита, не реализация наполнения. Владелец: vaNYA.
# Источник: https://github.com/dydojopka/SmartCity @ 6983e58de588795731a548e31534794873835057
# Файл smart-city/services/notification-service/app/seed.py в оригинале пустой.
# Задание: docs/tasks/vaNYA.md; данные: docs/API_CONTRACT.md
# (пути от корня репозитория).
#
# Реализовать seed_database(session: Session) -> None для своей таблицы.
# Демонстрационная запись: id=80000000-0000-0000-0000-000000000001,
# user_id и recipient=00000000-0000-0000-0000-000000000001, channel=PUSH,
# status=SENT; sent_at заполнен UTC-датой.
# Проверять существование ID: повторный seed не меняет существующие записи.
# Не вызывать отправку, не удалять данные, не запускать seed при импорте.
# Общий init_db подключит функцию после приёмки модуля.
