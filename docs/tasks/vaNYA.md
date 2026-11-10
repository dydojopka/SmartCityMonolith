# Белоножко Иван — vaNYA

## Выполненная часть

- Модуль Notification с публичным фасадом `NotificationApi.send` и
  защищённым маршрутом `POST /notifications` для Transport и Billing.
- Имитация отправки с раздельной фиксацией `PENDING` и `SENT`. Режим
  отказа оставляет уведомление в `PENDING` с пустым `sent_at`.
- Тесты фасада, проверки служебного токена и поведения при отказе.
- Схемы межсервисных вызовов, модулей и целевого города. Отчёт со сценарием,
  результатами замеров и экспериментом с отказом.

Код модуля — в [notification/](../../smart-city-monolith/app/modules/notification/).
[Исходник отчёта](../report/report.md) и [PDF](../report/report.pdf).
