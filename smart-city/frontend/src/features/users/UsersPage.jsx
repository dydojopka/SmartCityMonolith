import { API_URLS } from "../../api.js";
import { ListStatus, useApiList } from "../shared.jsx";

export default function UsersPage() {
  const list = useApiList(API_URLS.identity, "/users");

  return (
    <section className="card">
      <h1>Пользователи</h1>
      <ListStatus list={list} empty="Пользователей пока нет." />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Имя</th>
            <th>Фамилия</th>
            <th>Роль</th>
          </tr>
        </thead>
        <tbody>
          {list.data.map((user) => (
            <tr key={user.id}>
              <td>{user.id}</td>
              <td>{user.first_name}</td>
              <td>{user.last_name}</td>
              <td>{user.role}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
