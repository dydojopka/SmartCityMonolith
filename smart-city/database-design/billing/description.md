# БД Billing

Файл: `/data/billing.db`. Идентификаторы - UUID, даты - UTC.

| Таблица | Назначение |
|---|---|
| `invoices` | Владелец, описание, сумма, срок, статус и дата оплаты счёта |
| `payments` | Счёт, владелец, сумма, статус, ключ операции и внешнее событие |
| `webhook_events` | Уникальное событие провайдера, связанный платёж, payload и время обработки |

Связи: `payments.invoice_id → invoices.id`, `webhook_events.payment_id → payments.id`.
Пользовательский `user_id` не имеет FK на Identity DB.

- `amount_cents` - положительное целое число копеек; сайт показывает рубли.
- Счёт: `PENDING`, `PAID`, `CANCELLED`; платёж: `CREATED`, `SUCCEEDED`, `FAILED`.
- Ключ операции и внешний ID события уникальны.
- Частичный уникальный индекс допускает только один CREATED/SUCCEEDED платёж на счёт.
- Подтверждение платежа, оплата счёта и запись события сохраняются в одной транзакции.

Материалы: [SQL](schema.sql), [DBML](schema.dbml), [диаграмма](billing-diagram.png).
