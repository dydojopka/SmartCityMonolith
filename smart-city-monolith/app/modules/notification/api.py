# Новый файл монолита, не готовый фасад. Владелец: vaNYA.
# В исходном SmartCity @ 6983e58de588795731a548e31534794873835057 файла api.py нет.
# Основа: тело create_notification из закомментированного оригинала в router.py.
# Задание: docs/tasks/vaNYA.md; точный контракт: docs/API_CONTRACT.md
# (пути от корня репозитория).
#
# Нужно реализовать NotificationApi и переэкспортировать NotificationResponse.
# Перед записью валидировать аргументы через NotificationCreate. Открывать свою
# сессию через session_factory; фиксировать PENDING, затем SENT и sent_at.
# При fail_sending=True после первого commit выбрасывать
# RuntimeError("Notification sending failed"), оставляя PENDING и sent_at=NULL.
# Возвращать заполненный DTO до закрытия сессии, не ORM. Не импортировать Utility.
# Ниже только согласованная сигнатура: её раскомментирования недостаточно.
#
# class NotificationApi:
#     def __init__(self, session_factory, *, fail_sending: bool = False): ...
#
#     def send(
#         self, *, user_id: str | None, channel: str,
#         recipient: str, subject: str | None, message: str,
#     ) -> NotificationResponse: ...
