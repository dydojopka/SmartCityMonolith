# Контракт Utility и Notification

Рабочая договорённость для параллельной реализации по [PLAN §2](PLAN.md#2-архитектурное-решение-для-реализации).
Исходное поведение сверено с `dydojopka/SmartCity`, SHA `6983e58de588795731a548e31534794873835057`.
Контракт реализован обоими модулями и проверен сквозными тестами. Итоги — в [отчёте](report/report.md).

## Общие импорты и подключение

- `app.database`: `Base`, `engine`, `SessionLocal`, `get_db()`, `UTCDateTime`. SQLite через стандартный драйвер Python, один файл `monolith.db`; `check_same_thread=False`, timeout 30 секунд, `PRAGMA foreign_keys=ON`, как в исходнике. `UTCDateTime()` принимает только aware-даты, хранит naive UTC и возвращает aware UTC. WAL и отдельный сервер БД не добавляются.
- `app.auth`: `CurrentUser(id: str, role: str)`, `get_current_user`, `require_roles(*roles)`. HS256, обязательные `sub` (UUID), `role`, `exp`; роли `USER/OPERATOR/ADMIN`.
- `app.dependencies.get_notification_api()` создаёт `NotificationApi(SessionLocal, fail_sending=...)`. Флаг из `NOTIFICATION_FAIL_SEND`, по умолчанию `false` (`true`/`1` включают сбой). Функция возвращает настоящий фасад; успешной заглушки нет.
- Каждый модуль экспортирует `router: APIRouter` из `router.py`, регистрирует свои модели в `models.py`, предоставляет идемпотентный `seed_database(session: Session) -> None` в `seed.py`. Seed фиксирует только свои данные, без очистки БД и запуска при импорте.
- `app.init_db` явно импортирует обе `models` до `Base.metadata.create_all`, затем вызывает seed каждого модуля с собственной сессией. Оба router подключаются в `app.main` без префикса.

## Публичный фасад Notification

Единственная разрешённая межмодульная точка импорта — `app.modules.notification.api`:

```python
class NotificationApi:
    def __init__(self, session_factory, *, fail_sending: bool = False): ...

    def send(
        self, *, user_id: str | None, channel: str,
        recipient: str, subject: str | None, message: str,
    ) -> NotificationResponse: ...
```

`session_factory` — общий `sessionmaker`, а не открытая сессия Utility.
`NotificationResponse` — публичная Pydantic-модель, экспортируемая из того же `api.py`, с полями:

| Поле | Python-тип |
|---|---|
| `id`, `user_id` | `UUID`, `UUID \| None` |
| `recipient`, `channel`, `message` | `str` |
| `subject` | `str \| None` |
| `status` | `Literal["PENDING", "SENT", "FAILED"]` |
| `created_at`, `sent_at` | `datetime`, `datetime \| None` |

Наружу возвращается заполненный DTO, не ORM. JSON содержит UUID-строки, даты UTC с `Z`; Utility результат игнорирует.
До записи фасад применяет исходный `NotificationCreate`: `user_id` UUID/null, channel `EMAIL/SMS/PUSH`, recipient 1–255, subject до 255/null, message 1–5000; строки очищаются от пробелов по краям.

Для реальной смены статуса заявки Utility передаёт ровно:

```python
api.send(
    user_id=issue.user_id,
    channel="PUSH",
    recipient=issue.user_id,
    subject="Статус заявки изменён",
    message=f"Заявка {issue.id} получила статус {new_status}",
)
```

## Транзакции и ошибки

1. Utility выполняет атомарный `UPDATE ... WHERE status != new_status`, commit и refresh заявки. Только изменённая строка вызывает фасад.
2. Notification открывает свою сессию, фиксирует `PENDING`, затем отдельно фиксирует `SENT` и UTC `sent_at`. Сессия закрывается и при ошибке.
3. `fail_sending=True` после первого commit выбрасывает `RuntimeError("Notification sending failed")`, оставляя `PENDING`, `sent_at=NULL`. Фасад не подавляет исключение.
4. Utility перехватывает `Exception` **только вокруг вызова уведомления**, логирует ID/ошибку без секретов и возвращает сохранённую заявку с `200`. Ошибки операции с заявкой не подавляются. Прямой HTTP-запрос Notification при таком сбое получает `500`.
5. Тот же статус не создаёт повторное уведомление, в том числе при двух конкурентных PUT. Retry/outbox/очереди нет; восстановление демонстрируется на другой новой заявке.

## Внешний REST API

| Маршрут | Запрос и права | Ответ |
|---|---|---|
| `POST /issues` | JWT; title 3–200, description 3–5000, category 2–50 (uppercase), address 3–300; строки strip. Необязательный `X-Idempotency-Key` 1–128 | Новая запись `201`, статус `NEW`; тот же нормализованный payload и ключ пользователя → прежняя запись/`200`, иной payload → `409` |
| `GET /issues` | JWT; USER — только свои, OPERATOR/ADMIN — все | `200`, массив по `created_at DESC` |
| `PUT /issues/{issue_id}` | OPERATOR/ADMIN; `{"status":"NEW\|IN_PROGRESS\|RESOLVED\|REJECTED"}` (одно из значений) | `200`, неизвестный ID → `404`; повтор статуса без отправки |
| `POST /notifications` | `X-Service-Token`, исходный `NotificationCreate` с необязательными `user_id`/`subject` | `201`, `NotificationResponse`; нет/неверный токен → `401`; ошибка отправки → `500` |

Ответ заявки: `id`, `user_id`, `title`, `description`, `category`, `address`, `status`, `created_at`, `updated_at`; `request_key` не публикуется.
Общие ошибки: отсутствующий/невалидный/просроченный JWT → `401` и `WWW-Authenticate: Bearer`, недостаточная роль → `403`, ошибки входа → `422` с `detail` без `input`/`ctx`.
`/health`, `/docs` и CORS сохраняются. Префиксы `/api` и модулей не добавляются.
Один сервер `8000` доступен на host-портах `8003` и `8006` (параметры `UTILITY_PORT`/`NOTIFICATION_PORT`). Корневой `compose.yml` подключает его к полному SmartCity с сетевыми aliases `utility-service` и `notification-service`. Transport/Billing из `smart-city/services/` сохраняют HTTP-вызов `notification-service:8000`; прежний frontend из `smart-city/frontend/` использует те же внешние адреса. В полном целевом стенде подтверждены HTTP-уведомления от новой брони Transport и демо-оплаты Billing. Остальные четыре сервиса не становятся модулями и сохраняют свои SQLite-файлы.

## Данные и тесты

- `utility_issues` и `notification_notifications` в одном SQLite-файле, исходные поля/ограничения/индексы. В моделях задаётся `__tablename__` с префиксом, без `schema`. Обязательны уникальность `(user_id, request_key)` и обработка проигранной гонки POST через rollback и повторное чтение. FK/JOIN между модулями нет, обратных импортов нет.
- Utility seed: заявка `90000000-0000-0000-0000-000000000001`, автор `00000000-0000-0000-0000-000000000001`. Notification seed: `80000000-0000-0000-0000-000000000001`, тот же тестовый автор/recipient, PUSH, SENT; повторный seed не меняет существующие записи. Seed исключается из измеряемого прироста.
- Общие fixtures: `db_engine`, `clean_database`, `session_factory`, `db_session`, `client`, `notification_api`, `token_for(role="USER", user_id=..., expires_in=3600)`, `user_headers`, `operator_headers`, `admin_headers`, `service_headers`.
- `client` использует настоящий lifespan; `notification_api` — настоящий фасад, не mock. Для отказа создаётся `NotificationApi(session_factory, fail_sending=True)`; HTTP-зависимость можно переопределить через `app.dependency_overrides[get_notification_api]`.
- Fixtures создают новый реальный SQLite-файл в `tmp_path` для каждого теста и перенастраивают общий engine/`SessionLocal`. Внешние `DATABASE_URL`/`TEST_DATABASE_URL` не выбирают тестовую БД; очистки произвольных файлов/таблиц нет. Для конкурентных запросов и отдельных сессий Notification используется тот же файл текущего теста, не разные in-memory БД. После теста engine освобождается, прежняя привязка `SessionLocal` восстанавливается. Команда проверки — обычный `python -m pytest -q`, без внешнего сервера и credentials.
- Команды запуска и локального pytest: [PLAN — основа и проверка](PLAN.md#основа-и-проверка).
