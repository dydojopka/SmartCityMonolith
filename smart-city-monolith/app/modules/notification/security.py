# Заготовка переноса, не реализация модуля. Владелец: vaNYA.
# Источник: https://github.com/dydojopka/SmartCity @ 6983e58de588795731a548e31534794873835057
# Файл: smart-city/services/notification-service/app/security.py
# Задание: docs/tasks/vaNYA.md (от корня репозитория).
# При включении сохранить X-Service-Token и compare_digest. Проверка остаётся
# зависимостью HTTP-маршрута; прямой вызов фасада не требует HTTP-заголовков.
#
# --- Начало исходного файла (закомментировано) ---
# import os
# from hmac import compare_digest
#
# from fastapi import Header, HTTPException, status
#
#
# def verify_service_token(
#     x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
# ) -> None:
#     expected = os.getenv("SERVICE_TOKEN", "development-service-token")
#     if not x_service_token or not compare_digest(x_service_token.encode(), expected.encode()):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Неверный служебный токен",
#         )
# --- Конец исходного файла ---
