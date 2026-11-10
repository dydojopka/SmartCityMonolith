# Стенды для сравнения Utility и Notification

## Исходники и конфигурация

Микросервисный стенд собран из Utility и Notification ревизии
[SmartCity 6983e58](https://github.com/dydojopka/SmartCity/tree/6983e58de588795731a548e31534794873835057/smart-city).
В [baseline/](baseline/) находятся их `app/`, `requirements.txt` и исходные
Dockerfile. В Notification добавлена проверка `NOTIFICATION_FAIL_SEND`
после фиксации `PENDING`. При включённом флаге она вызывает
`RuntimeError("Notification sending failed")` до фиксации `SENT`.
Остальной код пары совпадает с исходным.

[Dockerfile.micro](Dockerfile.micro) собирает два образа из общей основы
и устанавливает пакеты с тем же [constraints.txt](../constraints.txt),
что и монолит. У каждого приложения один процесс Uvicorn. Микросервисы
хранят данные в отдельных SQLite-файлах, монолит использует общий файл.
В обеих версиях используется стандартный драйвер Python, тайм-аут SQLite
30 секунд, включены внешние ключи и сохранён исходный режим журнала.

| Стенд | Проект Compose | Порты Utility / Notification | SQLite внутри контейнеров |
|---|---|---|---|
| Микросервисы | `smart-city-micro-benchmark` | `18003` / `18006` | `/data/utility.db`, `/data/notification.db` |
| Монолит | `smart-city-mono-benchmark` | `28003` / `28006` | `/data/monolith.db` |

Эти стенды измеряют только выбранную пару. Полные версии города
описаны в [техническом обзоре](../../docs/PLAN.md#стенды).

## Воспроизведение замеров

Команды ниже выполняются из `smart-city-monolith/` в Bash на Linux или WSL.
Нужны Docker Compose и Python 3.12 с пакетами из
[requirements.txt](../requirements.txt). Запускайте стенды по очереди.
При задании собственных `JWT_SECRET` или `SERVICE_TOKEN` передайте одинаковые
значения в окружение Compose и скриптов проверки. Новые результаты записываются
во временный каталог, путь к нему выводится перед запуском.

```bash
output_dir="$(mktemp -d)"
echo "$output_dir"
revision="$(git rev-parse HEAD)"

NOTIFICATION_FAIL_SEND=false docker compose -f benchmarks/compose.micro.yml up -d --build --wait
python benchmarks/run.py --version micro --url http://localhost:18003 \
  --compose benchmarks/compose.micro.yml --project smart-city-micro-benchmark \
  --revision "$revision" --requests 200 --output "$output_dir/micro.json"
docker compose -f benchmarks/compose.micro.yml down

export UTILITY_PORT=28003 NOTIFICATION_PORT=28006
NOTIFICATION_FAIL_SEND=false docker compose -p smart-city-mono-benchmark up -d --build --wait app
python benchmarks/run.py --version mono --url http://localhost:28003 \
  --compose compose.yml --project smart-city-mono-benchmark \
  --revision "$revision" --requests 200 --output "$output_dir/mono.json"
docker compose -p smart-city-mono-benchmark down
unset UTILITY_PORT NOTIFICATION_PORT
```

[Генератор нагрузки](run.py) выполняет три прогона с конкурентностью 10.
Каждый прогон использует 20 заявок для прогрева и отдельные заявки для
измеряемых запросов. Инструмент проверяет новый статус каждой заявки и
ровно одно соответствующее уведомление `SENT`. Если в прогоне не хватает
двух полных снимков памяти внутри нагрузки, увеличьте `--requests`
одинаково для обеих версий и повторите серии.

## Воспроизведение отказа

[Сценарий проверки](failure.py) выполняется в двух фазах с одним файлом
результата. Сначала он создаёт заявку при включённом сбое, затем проверяет
повтор статуса и другую новую заявку после восстановления. Если замеры
в этой сессии Bash не запускались, задайте `output_dir="$(mktemp -d)"`.

### Микросервисы

```bash
NOTIFICATION_FAIL_SEND=true docker compose -f benchmarks/compose.micro.yml up -d --build --wait
python benchmarks/failure.py --version micro --url http://localhost:18003 \
  --notification-url http://localhost:18006 --compose benchmarks/compose.micro.yml \
  --project smart-city-micro-benchmark --phase failure --output "$output_dir/micro-failure.json"

NOTIFICATION_FAIL_SEND=false docker compose -f benchmarks/compose.micro.yml up -d --wait
python benchmarks/failure.py --version micro --url http://localhost:18003 \
  --notification-url http://localhost:18006 --compose benchmarks/compose.micro.yml \
  --project smart-city-micro-benchmark --phase recovery --output "$output_dir/micro-failure.json"
docker compose -f benchmarks/compose.micro.yml down
```

### Монолит

```bash
export UTILITY_PORT=28003 NOTIFICATION_PORT=28006
NOTIFICATION_FAIL_SEND=true docker compose -p smart-city-mono-benchmark up -d --build --wait app
python benchmarks/failure.py --version mono --url http://localhost:28003 \
  --notification-url http://localhost:28006 --compose compose.yml \
  --project smart-city-mono-benchmark --phase failure --output "$output_dir/mono-failure.json"

NOTIFICATION_FAIL_SEND=false docker compose -p smart-city-mono-benchmark up -d --wait app
python benchmarks/failure.py --version mono --url http://localhost:28003 \
  --notification-url http://localhost:28006 --compose compose.yml \
  --project smart-city-mono-benchmark --phase recovery --output "$output_dir/mono-failure.json"
docker compose -p smart-city-mono-benchmark down
unset UTILITY_PORT NOTIFICATION_PORT
```

Во время сбоя Utility возвращает `200` с сохранённым статусом заявки.
Уведомление остаётся в `PENDING` с `sent_at=NULL`, а прямой запрос к
Notification возвращает `500`. После восстановления новое уведомление
переходит в `SENT`. Прежняя запись сохраняет `PENDING`.

## Сохранённые результаты

- [Сводная таблица](results/summary.csv), [микросервисы](results/micro.json)
  и [монолит](results/mono.json).
- Отказ и восстановление для [микросервисов](results/micro-failure.json)
  и [монолита](results/mono-failure.json).
- [Проверка влияния хранилища](results/storage-check.json) и
  [описание условий в отчёте](../../docs/report/report.md#как-проводили-замеры).

Для итоговых серий базы обоих стендов хранились на одном NVMe SSD в отдельных
томах, подключённых к контейнерам. Образы собрали из заранее скачанных пакетов
одних версий. Отдельный файл SQLite у каждого микросервиса и общий файл у
монолита влияют на конкуренцию за запись. Результаты отражают работу обеих
реализаций в этих условиях.
