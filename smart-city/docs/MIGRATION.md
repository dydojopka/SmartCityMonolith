# Обновление старых БД

Для нового запуска с пустыми volumes миграция не нужна.
Если сервис сообщает `Legacy database`, старая схема несовместима:
`create_all()` создаёт таблицы, но не обновляет их структуру.
**Не удаляйте volumes для устранения этой ошибки.**

## Порядок

1. Из `smart-city/` остановите сервисы: `docker compose stop`.
2. Создайте резервные копии шести БД через SQLite backup API. Не копируйте
   работающий файл обычным `cp`: изменения могут находиться в WAL/journal.
3. В окружении Python 3.12 с requirements соответствующего сервиса перенесите
   резервную копию в новый файл:

```bash
python scripts/migrate_database.py identity /backups/identity.db /backups/new-identity.db --assume-legacy-utc
```

4. Повторите для `transport`, `utility`, `environment`, `billing`, `notification`.
   Скрипт не перезаписывает исходник или существующий файл назначения;
   рядом создаёт отчёт `*.migration.json`.
5. Сверьте отчёт, `PRAGMA integrity_check`, `PRAGMA foreign_key_check` и записи.
   Убедитесь, что сервис запускается на копии новой БД.
6. Установите новые БД в volumes остановленных сервисов через SQLite backup API.
   Запустите `docker compose up --build -d`. Сохраните исходные копии и отчёты вне Git.

## Важные параметры

- `--assume-legacy-utc` явно разрешает считать старые даты без часового пояса UTC.
- `--mapping file.json` задаёт отсутствующие параметры старых датчиков и транспорта.
  Для датчика нужны `unit`, `latitude`, `longitude`; для транспорта - `type`, `route_number`.
- Для Environment используйте прежний `SENSOR_API_KEY`: в БД сохраняется его хеш.
- Нарушенные связи, неизвестные поля и противоречивая финансовая история
  останавливают перенос. Не исправляйте их удалением записей без согласования.

Пример mapping:

```json
{"sensors":{"17":{"unit":"°C","latitude":59.9,"longitude":30.3}},"vehicles":{"старый-id":{"type":"CAR","route_number":""}}}
```
