# Заготовка переноса, не реализация модуля. Владелец: daNYA.
# Источник: https://github.com/dydojopka/SmartCity @ 6983e58de588795731a548e31534794873835057
# Файл: smart-city/services/utility-service/app/models.py
# Задание: docs/tasks/daNYA.md (от корня репозитория).
# Перед включением: переименовать таблицу в utility_issues; использовать общий
# app.database, сохранить уникальность (user_id, request_key), индексы и UTC.
# Не добавлять внешние ключи на другие модули.
#
# --- Начало исходного файла (закомментировано) ---
# from datetime import datetime, timezone
#
# from sqlalchemy import CheckConstraint, String, Text, Index
# from sqlalchemy.orm import Mapped, mapped_column
#
# from app.database import Base, UTCDateTime
#
#
# class Issue(Base):
#     __tablename__ = "issues"
#     __table_args__ = (
#         CheckConstraint("status IN ('NEW','IN_PROGRESS','RESOLVED','REJECTED')", name="ck_issue_status"),
#         Index("uq_issue_user_request", "user_id", "request_key", unique=True),
#     )
#
#     id: Mapped[str] = mapped_column(String(36), primary_key=True)
#     user_id: Mapped[str] = mapped_column(String(36), index=True)
#     request_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
#     title: Mapped[str] = mapped_column(String(200))
#     description: Mapped[str] = mapped_column(Text)
#     category: Mapped[str] = mapped_column(String(50), index=True)
#     address: Mapped[str] = mapped_column(String(300))
#     status: Mapped[str] = mapped_column(String(20), default="NEW", index=True)
#     created_at: Mapped[datetime] = mapped_column(
#         UTCDateTime(), default=lambda: datetime.now(timezone.utc)
#     )
#     updated_at: Mapped[datetime] = mapped_column(
#         UTCDateTime(),
#         default=lambda: datetime.now(timezone.utc),
#         onupdate=lambda: datetime.now(timezone.utc),
#     )
# --- Конец исходного файла ---
