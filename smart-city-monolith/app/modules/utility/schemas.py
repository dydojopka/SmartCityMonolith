# Заготовка переноса, не реализация модуля. Владелец: daNYA.
# Источник: https://github.com/dydojopka/SmartCity @ 6983e58de588795731a548e31534794873835057
# Файл: smart-city/services/utility-service/app/schemas.py
# Задание: docs/tasks/daNYA.md (от корня репозитория).
# При включении сохранить исходные поля, ограничения, нормализацию и формат ответа.
#
# --- Начало исходного файла (закомментировано) ---
# from datetime import datetime
# from typing import Literal
#
# from pydantic import BaseModel, ConfigDict, Field, field_validator
#
# IssueStatus = Literal["NEW", "IN_PROGRESS", "RESOLVED", "REJECTED"]
#
#
# class IssueCreate(BaseModel):
#     model_config = ConfigDict(str_strip_whitespace=True)
#     title: str = Field(min_length=3, max_length=200)
#     description: str = Field(min_length=3, max_length=5000)
#     category: str = Field(min_length=2, max_length=50)
#     address: str = Field(min_length=3, max_length=300)
#
#     @field_validator("category", mode="before")
#     @classmethod
#     def normalize_category(cls, value):
#         return value.strip().upper() if isinstance(value, str) else value
#
#
# class IssueStatusUpdate(BaseModel):
#     status: IssueStatus
#
#
# class IssueResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#
#     id: str
#     user_id: str
#     title: str
#     description: str
#     category: str
#     address: str
#     status: IssueStatus
#     created_at: datetime
#     updated_at: datetime
# --- Конец исходного файла ---
