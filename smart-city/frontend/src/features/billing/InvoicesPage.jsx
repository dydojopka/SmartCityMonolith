import { useState } from "react";
import { API_URLS, apiFetch } from "../../api.js";
import { ActionStatus, ListStatus, time, useAction, useApiList } from "../shared.jsx";

const rubles = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export default function InvoicesPage({ currentUser }) {
  const list = useApiList(API_URLS.billing, `/accounts/${currentUser.id}/invoices`);
  const action = useAction();
  const [payment, setPayment] = useState(null);

  async function pay(invoice) {
    await action.run(async () => {
      const storageKey = `payment-key:${currentUser.id}:${invoice.id}`;
      const key = sessionStorage.getItem(storageKey) || crypto.randomUUID();
      sessionStorage.setItem(storageKey, key);
      let result = await apiFetch(API_URLS.billing, "/payments", {
        method: "POST",
        body: JSON.stringify({
          invoice_id: invoice.id,
          idempotency_key: key,
        }),
      });
      setPayment(result);
      if (result.status === "FAILED") sessionStorage.removeItem(storageKey);
      if (result.status === "CREATED") {
        result = await apiFetch(API_URLS.billing, `/payments/${result.id}/demo-success`, {
          method: "POST",
        });
        setPayment(result);
      }
      await list.reload();
      return result;
    }, (result) => result.status === "FAILED"
      ? "Платёж не выполнен. Можно начать новую попытку отдельным нажатием."
      : result.status === "SUCCEEDED" ? "Счёт оплачен. Демо-оплата подтверждена; деньги не списывались."
      : "Платёж создан, но оплата ещё не подтверждена. Повторите оплату.");
  }

  return (
    <section className="card">
      <h1>Счета</h1>
      <p>Демонстрационная оплата: без банковской карты и списания денег.</p>
      <ListStatus list={list} empty="Счетов пока нет." />
      <ActionStatus action={action} />
      {payment && <p>Платёж: <code>{payment.id}</code>, статус: {payment.status}</p>}
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Описание</th>
            <th>Срок оплаты</th>
            <th>Сумма, ₽</th>
            <th>Статус</th>
            <th>Оплачен</th>
            <th>Действие</th>
          </tr>
        </thead>
        <tbody>
          {list.data.map((inv) => (
            <tr key={inv.id}>
              <td>{inv.id}</td>
              <td>{inv.description}</td>
              <td>{inv.due_date || "-"}</td>
              <td>{rubles.format(inv.amount_cents / 100)}</td>
              <td>{inv.status === "PAID" ? "Оплачен (PAID)" : inv.status}</td>
              <td>{time(inv.paid_at)}</td>
              <td>
                <button
                  className="button"
                  onClick={() => pay(inv)}
                  disabled={action.pending || inv.status !== "PENDING"}
                >
                  {inv.status === "PAID" ? "Оплачен" : payment?.invoice_id === inv.id && payment.status !== "SUCCEEDED" ? "Повторить оплату" : "Оплатить"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
