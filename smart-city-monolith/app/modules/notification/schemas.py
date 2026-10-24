# Заготовка переноса, не реализация модуля. Владелец: vaNYA.
# Источник: https://github.com/dydojopka/SmartCity @ 6983e58de588795731a548e31534794873835057
# Файл: smart-city/services/notification-service/app/schemas.py
# Задание: docs/tasks/vaNYA.md (от корня репозитория).
# При включении сохранить валидацию. NotificationResponse переэкспортировать
# из api.py; фасад возвращает заполненную Pydantic-модель, не ORM.
#
# --- Начало исходного файла (закомментировано) ---
# from datetime import datetime
# from uuid import UUID
# from typing import Literal
#
# from pydantic import BaseModel, ConfigDict, Field
#
#
# class NotificationCreate(BaseModel):
#     model_config = ConfigDict(str_strip_whitespace=True)
#     user_id: UUID | None = None
#     recipient: str = Field(min_length=1, max_length=255)
#     channel: Literal["EMAIL", "SMS", "PUSH"]
#     subject: str | None = Field(default=None, max_length=255)
#     message: str = Field(min_length=1, max_length=5000)
#
#
# class NotificationResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#
#     id: UUID
#     user_id: UUID | None
#     recipient: str
#     channel: str
#     subject: str | None
#     message: str
#     status: Literal["PENDING", "SENT", "FAILED"]
#     created_at: datetime
#     sent_at: datetime | None
# --- Конец исходного файла ---
