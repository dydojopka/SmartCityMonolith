# Происхождение исходного SmartCity

В `smart-city/` сохранены все 132 отслеживаемых файла каталога приложения из
[SmartCity](https://github.com/dydojopka/SmartCity) на commit
`6983e58de588795731a548e31534794873835057`.
Проверка содержимого с учётом различий LF/CRLF подтверждает, что бизнес-код
шести сервисов, frontend, зависимости и исторические материалы не изменены.

Преднамеренно отличаются только два файла:

- `smart-city/.gitignore`: правила исключения локальных данных и зависимостей.
- `smart-city/docker-compose.yml`: самостоятельный project name, loopback-порты
  с параметрами, отдельные project-scoped volumes и сети, healthchecks и
  согласованные адреса API/CORS. Приложения остаются исходными.

Корневой `compose.yml` описывает целевой город: Identity, Transport,
Environment, Billing, прежний frontend и монолит вместо Utility/Notification.
Aliases `utility-service` и `notification-service` направлены на монолит.
Transport и Billing по-прежнему обращаются к `POST /notifications` по HTTP.
Внутренний вызов Utility заменён на `NotificationApi.send`.

Документы в `smart-city/docs/`, `smart-city/tasks/` и `database-design/` являются
материалами предыдущей работы. Текущее задание — корневой `task.md`, план и
контракт — в корневом `docs/`. SQL-материалы прежнего проекта не меняют
фактическую СУБД: приложения используют SQLite.

Для измерений используется отдельная копия выбранной пары в
`smart-city-monolith/benchmarks/baseline/`; источник, флаг отказа и команды
описаны в [ORIGIN.md](../smart-city-monolith/benchmarks/ORIGIN.md).
Соседний checkout SmartCity, его среды, БД и контейнеры не используются.
