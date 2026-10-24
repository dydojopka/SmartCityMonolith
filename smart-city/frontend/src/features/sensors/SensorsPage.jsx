import { useState } from "react";
import { API_URLS } from "../../api.js";
import { ListStatus, time, useApiList } from "../shared.jsx";

export default function SensorsPage() {
  const [selectedId, setSelectedId] = useState(null);
  const sensors = useApiList(API_URLS.environment, "/sensors");
  const readings = useApiList(API_URLS.environment, selectedId ? `/sensors/${selectedId}/data` : null);
  const selected = sensors.data.find((sensor) => sensor.id === selectedId);

  return (
    <section className="card">
      <h1>Датчики</h1>
      <ListStatus list={sensors} empty="Датчиков пока нет." />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Название</th>
            <th>Тип</th>
            <th>Единица</th>
            <th>Координаты</th>
            <th>Последний контакт</th>
            <th>Статус</th>
            <th>Действие</th>
          </tr>
        </thead>
        <tbody>
          {sensors.data.map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td>{s.name}</td>
              <td>{s.type}</td>
              <td>{s.unit}</td>
              <td>{s.latitude}, {s.longitude}</td>
              <td>{time(s.last_seen_at)}</td>
              <td>{s.status}</td>
              <td>
                <button className="button" onClick={() => selectedId === s.id ? readings.reload() : setSelectedId(s.id)}>
                  Показания
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedId && (
        <>
          <h2>Показания датчика #{selectedId}</h2>
          <ListStatus list={readings} empty="Показаний пока нет." />
          {!readings.loading && readings.data.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Значение</th>
                  <th>Ед. изм.</th>
                  <th>Измерено</th>
                  <th>Получено</th>
                </tr>
              </thead>
              <tbody>
                {readings.data.map((r) => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td>{r.value}</td>
                    <td>{selected?.unit || "-"}</td>
                    <td>{time(r.measured_at)}</td>
                    <td>{time(r.received_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
