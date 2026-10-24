import { API_URLS } from "../../api.js";
import { ActionStatus, ListStatus, useAction, useApiList, postOperation, pendingOperation } from "../shared.jsx";

export default function ParkingPage({ currentUser }) {
  const list = useApiList(API_URLS.transport, "/parking");
  const action = useAction();
  const storageKey = (id) => `reservation-key:${currentUser.id}:${id}`;

  async function reserve(id) {
    await action.run(async () => {
      await postOperation(API_URLS.transport, `/parking/${id}/reserve`, storageKey(id));
      await list.reload();
    }, "Место забронировано.");
  }

  return (
    <section className="card">
      <h1>Парковки</h1>
      <ListStatus list={list} empty="Парковок пока нет." />
      <ActionStatus action={action} />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Название</th>
            <th>Адрес</th>
            <th>Координаты</th>
            <th>Всего мест</th>
            <th>Свободно</th>
            <th>Действие</th>
          </tr>
        </thead>
        <tbody>
          {list.data.map((p) => (
            <tr key={p.id}>
              <td>{p.id}</td>
              <td>{p.name}</td>
              <td>{p.address}</td>
              <td>{p.latitude}, {p.longitude}</td>
              <td>{p.total_spaces}</td>
              <td>{p.available_spaces}</td>
              <td>
                <button
                  className="button"
                  onClick={() => reserve(p.id)}
                  disabled={action.pending || (p.available_spaces <= 0 && !pendingOperation(storageKey(p.id)))}
                >
                  Забронировать
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
