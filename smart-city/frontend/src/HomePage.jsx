import { Link } from "react-router-dom";
import { API_URLS } from "./api.js";
import { useApiList } from "./features/shared.jsx";

const rubles = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB" });

function Summary({ list, children }) {
  if (list.loading) return <p role="status">Загрузка...</p>;
  if (list.error) return <>
    <p className="error" role="alert">{list.error}</p>
    <button className="button secondary" onClick={list.reload}>Повторить</button>
  </>;
  return children;
}

function PersonalOverview({ currentUser }) {
  const invoices = useApiList(API_URLS.billing, `/accounts/${currentUser.id}/invoices`);
  const issues = useApiList(API_URLS.utility, "/issues");
  const parking = useApiList(API_URLS.transport, "/parking");
  const unpaid = invoices.data.filter((invoice) => invoice.status === "PENDING");
  const activeIssues = issues.data.filter((issue) => ["NEW", "IN_PROGRESS"].includes(issue.status));
  const canManage = ["OPERATOR", "ADMIN"].includes(currentUser.role);

  function reload() {
    invoices.reload();
    issues.reload();
    parking.reload();
  }

  return <>
    <div className="overview-heading">
      <div>
        <h1>Обзор города</h1>
        <p className="muted">{currentUser.first_name} {currentUser.last_name}. Счета, заявки и парковки в одном месте.</p>
      </div>
      <button className="button secondary" disabled={invoices.loading || issues.loading || parking.loading} onClick={reload}>Обновить обзор</button>
    </div>

    <section className="overview-section" aria-labelledby="personal-heading">
      <h2 id="personal-heading">{canManage ? "Счета и работа с заявками" : "Мои дела"}</h2>
      <div className="overview-columns">
        <section aria-labelledby="invoices-heading">
          <h3 id="invoices-heading"><Link to="/invoices">Мои счета</Link></h3>
          <Summary list={invoices}>
            {unpaid.length ? <>
              <p className="overview-value">{rubles.format(unpaid.reduce((total, invoice) => total + invoice.amount_cents, 0) / 100)}</p>
              <p>Неоплаченных счетов: {unpaid.length}.</p>
              <Link to="/invoices">Посмотреть счета и создать платёж</Link>
            </> : <p>{invoices.data.length ? "Неоплаченных счетов нет." : "Вам пока не выставлены счета."}</p>}
          </Summary>
        </section>
        <section aria-labelledby="issues-heading">
          <h3 id="issues-heading"><Link to="/utility">{canManage ? "Заявки жителей" : "Мои заявки ЖКХ"}</Link></h3>
          <Summary list={issues}>
            <p>{activeIssues.length ? `Открытых заявок: ${activeIssues.length}.` : "Открытых заявок нет."}</p>
            {activeIssues.length > 0 && <ul className="overview-list">
              {activeIssues.slice(0, 3).map((issue) => <li key={issue.id}>
                <Link to="/utility">{issue.title}</Link>
                <span className="muted">{issue.status === "NEW" ? "Новая" : "В работе"} · {issue.address}</span>
              </li>)}
            </ul>}
          </Summary>
          <Link className="button" to="/utility">{canManage ? "Открыть заявки" : "Подать заявку ЖКХ"}</Link>
        </section>
      </div>
    </section>

    <section className="overview-section" aria-labelledby="parking-heading">
      <h2 id="parking-heading">Свободные места на парковках</h2>
      <Summary list={parking}>
        {parking.data.length ? <ul className="parking-overview">
          {parking.data.map((place) => <li key={place.id}>
            <div><Link to="/parking">{place.name}</Link><p className="muted">{place.address}</p></div>
            <p>{place.available_spaces > 0 ? `Свободно ${place.available_spaces} из ${place.total_spaces}` : "Свободных мест нет"}</p>
          </li>)}
        </ul> : <p>Парковки пока не добавлены.</p>}
      </Summary>
      <Link to="/parking">Выбрать парковку и забронировать место</Link>
    </section>
    <ServiceDirectory />
  </>;
}

function ServiceDirectory({ guest = false }) {
  const services = [
    { to: "/transport", title: "Транспорт", description: "Маршруты, координаты и состояние городского транспорта." },
    { to: "/sensors", title: "Экологические датчики", description: "Состояние датчиков и история их показаний." },
    ...(guest ? [
      { to: "/parking", title: "Парковки", description: "Количество свободных мест и бронирование." },
      { to: "/utility", title: "Заявки ЖКХ", description: "Сообщите о неисправности и следите за статусом заявки." },
      { to: "/invoices", title: "Счета", description: "Ваши начисления, сроки оплаты и создание платежа." },
    ] : [
      { to: "/users", title: "Пользователи", description: "Справочник жителей и сотрудников: имена и роли." },
      { to: "/profile", title: "Профиль", description: "Ваше имя, email и роль в системе." },
    ]),
  ];
  return <section className="overview-section" aria-labelledby="services-heading">
    <h2 id="services-heading">{guest ? "Что можно сделать" : "Другие разделы"}</h2>
    <ul className="service-directory">
      {services.map((service) => <li key={service.to}>
        <h3><Link to={service.to}>{service.title}</Link></h3>
        <p className="muted">{service.description}</p>
      </li>)}
    </ul>
  </section>;
}

export default function HomePage({ currentUser, loading, profileError, sessionNotice, onRetry }) {
  if (loading) return <p role="status">Загрузка профиля...</p>;
  if (profileError) return <section className="card">
    <h1>Обзор города</h1>
    <p className="error" role="alert">{profileError}</p>
    <button className="button" onClick={onRetry}>Повторить</button>
  </section>;
  if (currentUser) return <PersonalOverview currentUser={currentUser} />;
  return <>
    <h1>Умный город</h1>
    <p>Подайте заявку ЖКХ, найдите свободное место на парковке или проверьте счета.</p>
    {sessionNotice && <p role="status">{sessionNotice}</p>}
    <p>Войдите, чтобы открыть свои данные и пользоваться сервисами.</p>
    <div className="home-actions">
      <Link className="button" to="/login" state={{ returnTo: "/" }}>Войти в систему</Link>
      <Link to="/register" state={{ returnTo: "/" }}>Зарегистрироваться</Link>
    </div>
    <ServiceDirectory guest />
  </>;
}
