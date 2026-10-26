# Исходная версия для сравнения

- Источник: <https://github.com/dydojopka/SmartCity>, каталог `smart-city/`.
- Зафиксированный commit: `6983e58de588795731a548e31534794873835057`.
- Для этого изолированного стенда скопированы только отслеживаемые `app/`, `requirements.txt`, `Dockerfile` из `services/utility-service/` и `services/notification-service/`. Окружения, базы, секреты и исходные контейнеры не используются. Полный исходный SmartCity также сохранён в корневом `smart-city/`; целевой полный город описан корневым `compose.yml`. Состав переноса — в [docs/SMARTCITY_ORIGIN.md](../../docs/SMARTCITY_ORIGIN.md).
- Utility, остальные файлы Notification и оба исходных Dockerfile/requirements совпадают с источником побайтово. Единственное поведенческое отличие — три строки в `notification-service/app/main.py` после commit/refresh `PENDING`, перед имитацией отправки:

```python
if os.getenv("NOTIFICATION_FAIL_SEND", "false").strip().lower() in {"true", "1"}:
    raise RuntimeError("Notification sending failed")
```

Пустая строка отделяет блок от исходного комментария. По умолчанию сбой выключен. При включении прямой `POST /notifications` даёт `500`, сохранённое уведомление остаётся `PENDING` с `sent_at=NULL`; Utility сохраняет свой best-effort и отвечает `200` после commit заявки.
Инфраструктурное отличие: Compose собирает оба сервиса через `benchmarks/Dockerfile.micro` с общим build-контекстом `smart-city-monolith/`. Одинаковые исходные requirements устанавливаются один раз в общем слое с `constraints.txt`; сборка проверяет их побайтовое равенство. Затем отдельные targets копируют только свой `app/`. Исходные Dockerfile сохранены для сверки, но в этом стенде не используются. Ограничения фиксируют версии из микросервисного стенда (включая транзитивные зависимости); mono использует те же общие версии и встроенную SQLite, без нового драйвера СУБД. Без ограничений кешированные и новые сборки получали разные Pydantic/uvloop. Общий `.dockerignore` исключает конфигурацию, базы и кеши. Compose задаёт один Uvicorn worker явно (как исходный режим по умолчанию), два отдельных SQLite-volume, внутренний HTTP-адрес и healthcheck. JWT и служебный токен не отключены.

## Запуск и чтение данных

Все команды — из `smart-city-monolith/`. Используются только демонстрационные значения из Compose; для собственного секрета передавать одинаковые переменные окружения обоим стендам. Секреты/JWT не сохранять в результатах или истории команд.

```bash
docker compose -f benchmarks/compose.micro.yml up -d --build --wait
curl http://localhost:18003/health
curl http://localhost:18006/health

# Read-only чтение собственной SQLite Utility, без SQLite CLI в контейнере.
docker compose -f benchmarks/compose.micro.yml exec -T utility-service python -c 'import sqlite3; db=sqlite3.connect("file:/data/utility.db?mode=ro", uri=True); print(db.execute("SELECT id, status FROM issues ORDER BY created_at DESC LIMIT 5").fetchall())'

# Проверяются также message/user_id: общий счётчик сам по себе недостаточен.
docker compose -f benchmarks/compose.micro.yml exec -T notification-service python -c 'import sqlite3; db=sqlite3.connect("file:/data/notification.db?mode=ro", uri=True); print(db.execute("SELECT id, user_id, message, status, sent_at FROM notifications ORDER BY created_at DESC LIMIT 5").fetchall())'

# Остановка без удаления volume; исходный SmartCity не затрагивается.
docker compose -f benchmarks/compose.micro.yml down
```

Compose project по умолчанию — `smart-city-micro-benchmark`, порты `18003/18006`. Контейнеров два, оба с SQLite внутри процесса; отдельного контейнера СУБД нет. Один обычный запуск — одна Compose-команда.

Это сравнение подсистемы Utility + Notification, а не всех компонентов города. Полные исходный/целевой стенды запускаются отдельно для проверки совместимости; их контейнеры и результаты нельзя смешивать с измерениями этой пары.

## Проверка отказа

После штатного запуска пересоздать **только свой** Notification с включённым флагом:

```bash
NOTIFICATION_FAIL_SEND=true docker compose -f benchmarks/compose.micro.yml up -d --wait notification-service
```

На новой заявке выполнить `NEW → IN_PROGRESS` с OPERATOR JWT. Проверить ответ Utility `200`, новое чтение заявки, запись Notification `PENDING/NULL` приведёнными выше read-only командами. В логах Notification должен быть внутренний HTTP `500` и `RuntimeError`, а Utility — `notification_failed`. Не публиковать необработанные логи с заголовками авторизации.

```bash
docker compose -f benchmarks/compose.micro.yml logs --no-color --tail 30 notification-service
docker compose -f benchmarks/compose.micro.yml logs --no-color --tail 30 utility-service
NOTIFICATION_FAIL_SEND=false docker compose -f benchmarks/compose.micro.yml up -d --wait notification-service
```

Для подтверждения восстановления нужна **другая новая заявка**. Повтор прежнего статуса — no-op, не повторная отправка PENDING. Проверить `SENT` и ненулевой `sent_at` новой записи. Прямой HTTP Notification сохраняет проверку `X-Service-Token`: без токена `401`, с корректным токеном и невалидным телом `422`.

## Изолированный mono-стенд

Micro и mono для измерений запускаются **по очереди**. После остановки micro:

```bash
export UTILITY_PORT=28003 NOTIFICATION_PORT=28006
docker compose -p smart-city-mono-benchmark up -d --build --wait app
curl http://localhost:28003/health
curl http://localhost:28006/health
docker compose -p smart-city-mono-benchmark exec -T app python -c 'import sqlite3; db=sqlite3.connect("file:/data/monolith.db?mode=ro", uri=True); print(db.execute("SELECT name FROM sqlite_master WHERE type=?", ("table",)).fetchall())'
docker compose -p smart-city-mono-benchmark exec -T app python -c 'import sqlite3; db=sqlite3.connect("file:/data/monolith.db?mode=ro", uri=True); print(db.execute("SELECT id, status FROM utility_issues ORDER BY created_at DESC LIMIT 5").fetchall())'
docker compose -p smart-city-mono-benchmark exec -T app python -c 'import sqlite3; db=sqlite3.connect("file:/data/monolith.db?mode=ro", uri=True); print(db.execute("SELECT id, message, status, sent_at FROM notification_notifications ORDER BY created_at DESC LIMIT 5").fetchall())'
docker compose -p smart-city-mono-benchmark down
unset UTILITY_PORT NOTIFICATION_PORT
```

У mono свой project и volume `monolith-sqlite-data`: один контейнер/процесс приложения, один файл `/data/monolith.db`. Старые volumes другой СУБД не используются, не конвертируются и не удаляются. Оба модуля подключены, структура и seed создаются общим `app.init_db`; версия для измерений и результаты сохранены в `results/`.

**Условия сравнения:** обе версии используют SQLite со стандартным драйвером Python, timeout 30 секунд и foreign keys; WAL не включается. Перед измерениями сверить `sqlite3.sqlite_version` и `PRAGMA journal_mode` в каждом приложении. В micro два файла/контейнера, в mono один, поэтому меняется и конкуренция за писателя. Результаты сравнивают две конкретные реализации, не изолированный эффект замены HTTP вызовом метода. Методика N ≥ 200, concurrency 10, трёх прогонов и проверки каждого нового SENT — в [PLAN §4](../../docs/PLAN.md#4-общая-методика-измерений-и-отказа). Инструмент, три прогона каждой версии и результаты отказа находятся рядом в `run.py`, `failure.py` и `results/`.

## Воспроизведение измерений

Нужен Linux-хост или WSL с Docker Compose и Python 3.12 с зависимостями
из `requirements.txt`. Команды выполняются из `smart-city-monolith/`.
Стандартный проект ниже совпадает с проектом, который выбирает инструмент;
при использовании `-p` передать то же имя через `--project`. Для обоих
стендов используются одинаковые демонстрационные значения; собственные
JWT_SECRET/SERVICE_TOKEN передавать через окружение, не сохранять в результатах.

```bash
docker compose -f benchmarks/compose.micro.yml up -d --build --wait
python benchmarks/run.py --version micro --url http://localhost:18003 --compose benchmarks/compose.micro.yml --project smart-city-micro-benchmark --revision "$(git rev-parse HEAD)" --requests 200 --output benchmarks/results/micro.json
docker compose -f benchmarks/compose.micro.yml down

export UTILITY_PORT=28003 NOTIFICATION_PORT=28006
docker compose -p smart-city-mono-benchmark up -d --build --wait app
python benchmarks/run.py --version mono --url http://localhost:28003 --compose compose.yml --project smart-city-mono-benchmark --revision "$(git rev-parse HEAD)" --requests 200 --output benchmarks/results/mono.json
docker compose -p smart-city-mono-benchmark down
```

По умолчанию выполняются три прогона. Если хотя бы в одном не хватает двух
полных снимков памяти внутри нагрузки, увеличить N одинаково для обеих
верссий и повторить все серии. `valid=false` не является итоговым замером.
Подготовка и 20 отдельных прогревочных заявок не входят в измеряемый пакет.

Для проверки отказа сначала включить флаг соответствующего стенда,
запустить `failure.py --phase failure`, выключить флаг и запустить
`--phase recovery` с тем же файлом результата. Пример для micro:

```bash
NOTIFICATION_FAIL_SEND=true docker compose -f benchmarks/compose.micro.yml up -d --wait
python benchmarks/failure.py --version micro --url http://localhost:18003 --notification-url http://localhost:18006 --compose benchmarks/compose.micro.yml --project smart-city-micro-benchmark --phase failure --output benchmarks/results/micro-failure.json
NOTIFICATION_FAIL_SEND=false docker compose -f benchmarks/compose.micro.yml up -d --wait
python benchmarks/failure.py --version micro --url http://localhost:18003 --notification-url http://localhost:18006 --compose benchmarks/compose.micro.yml --project smart-city-micro-benchmark --phase recovery --output benchmarks/results/micro-failure.json
docker compose -f benchmarks/compose.micro.yml down
```

Для mono используются `--version mono`, project `smart-city-mono-benchmark`,
`--compose compose.yml`, URL `28003/28006` и файл `mono-failure.json`;
флаг пересоздаёт `app`. Восстановление проверяется на другой новой заявке,
прежний PENDING автоматически не доставляется.

Итоговая таблица и условия — в [Markdown-отчёте](../../docs/report/report.md).
Выполненные серии использовали одинаковые офлайн-образы, собранные из того же
кода и общих зафиксированных пакетов: WSL не имела прямого сетевого доступа.
После предварительного невалидного прогона на медленном хранилище обе версии
получили отдельные named volumes с одинаковым bind к одному NVMe/NTFS.
Параметры SQLite и исходный HTTP timeout 3 секунды сохранены. Диагностика —
в `results/storage-check.json`; подробные условия указаны в отчёте.
Исходные JSON содержат версии, параметры SQLite и команды процессов;
временные образы, пакеты и локальные конфигурации не публикуются.
