import { API_URLS } from "../../api.js";
import { ListStatus, time, useApiList } from "../shared.jsx";

export default function TransportPage() {
  const list = useApiList(API_URLS.transport, "/vehicles");

  return (
    <section className="card">
      <h1>Транспорт</h1>
      <ListStatus list={list} empty="Транспорт пока не добавлен." />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Тип</th>
            <th>Маршрут</th>
            <th>Координаты</th>
            <th>Обновлено</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          {list.data.map((v) => (
            <tr key={v.id}>
              <td>{v.id}</td>
              <td>{v.type}</td>
              <td>{v.route_number}</td>
              <td>{v.latitude}, {v.longitude}</td>
              <td>{time(v.updated_at)}</td>
              <td>{v.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
