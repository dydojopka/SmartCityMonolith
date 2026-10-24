import { useState } from "react";
import { API_URLS, apiFetch } from "../../api.js";
import { ActionStatus, ListStatus, useAction, useApiList, postOperation, pendingOperation } from "../shared.jsx";

export default function UtilityIssuesPage({ currentUser }) {
  const list = useApiList(API_URLS.utility, "/issues");
  const action = useAction();
  const canUpdate = ["OPERATOR", "ADMIN"].includes(currentUser.role);
  const storageKey = `issue-key:${currentUser.id}`;
  const [form, setForm] = useState(() => {
    const pending = pendingOperation(storageKey);
    return pending?.body ? JSON.parse(pending.body) : {
    title: "",
    description: "",
    category: "",
    address: "",
    };
  });

  async function submit(event) {
    event.preventDefault();
    await action.run(async () => {
      await postOperation(API_URLS.utility, "/issues", storageKey, form);
      setForm({ title: "", description: "", category: "", address: "" });
      await list.reload();
    }, "Заявка создана.");
  }

  async function updateStatus(id, status) {
    await action.run(async () => {
      await apiFetch(API_URLS.utility, `/issues/${id}`, { method: "PUT", body: JSON.stringify({ status }) });
      await list.reload();
    }, "Статус обновлён.");
  }

  return (
    <section className="card">
      <h1>Заявки ЖКХ</h1>

      <form onSubmit={submit}>
        <label>
          Тема
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
          />
        </label>
        <label>
          Описание
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            required
          />
        </label>
        <label>
          Категория
          <input
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            required
          />
        </label>
        <label>
          Адрес
          <input
            value={form.address}
            onChange={(e) => setForm({ ...form, address: e.target.value })}
            required
          />
        </label>
        <button className="button" type="submit" disabled={action.pending}>
          Отправить
        </button>
      </form>

      <ListStatus list={list} empty="Заявок пока нет." />
      <ActionStatus action={action} />
      {list.data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Тема</th>
              <th>Категория</th>
              <th>Адрес</th>
              <th>Статус</th>
              {canUpdate && <th>Изменить статус</th>}
            </tr>
          </thead>
          <tbody>
            {list.data.map((issue) => (
              <tr key={issue.id}>
                <td>{issue.id}</td>
                <td>{issue.title}</td>
                <td>{issue.category}</td>
                <td>{issue.address}</td>
                <td>{issue.status}</td>
                {canUpdate && <td><select aria-label={`Статус заявки ${issue.title}`} value={issue.status} disabled={action.pending} onChange={(e) => updateStatus(issue.id, e.target.value)}>
                  {["NEW", "IN_PROGRESS", "RESOLVED", "REJECTED"].map((status) => <option key={status}>{status}</option>)}
                </select></td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
