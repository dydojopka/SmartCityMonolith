import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import HomePage from "./HomePage.jsx";
import UsersPage from "./features/users/UsersPage.jsx";
import TransportPage from "./features/transport/TransportPage.jsx";
import ParkingPage from "./features/parking/ParkingPage.jsx";
import UtilityIssuesPage from "./features/utility/UtilityIssuesPage.jsx";
import SensorsPage from "./features/sensors/SensorsPage.jsx";
import InvoicesPage from "./features/billing/InvoicesPage.jsx";

import { API_URLS, AUTH_REJECTED_EVENT, apiFetch, getToken, setToken } from "./api.js";

function loginDestination(returnTo) {
  return typeof returnTo === "string" && returnTo.startsWith("/")
    && !returnTo.startsWith("//") && !/^\/(login|register)([/?#]|$)/.test(returnTo)
    ? returnTo : "/profile";
}

function Layout({ currentUser, loading, onLogout, children }) {
  return (
    <>
      <header className="site-header">
        <Link className="brand" to="/">
          Умный город
        </Link>
        <nav aria-label="Основная навигация">
          <NavLink to="/">Главная</NavLink>
          {currentUser ? (
            <>
              <NavLink to="/profile">Профиль</NavLink>
              <NavLink to="/users">Пользователи</NavLink>
              <NavLink to="/transport">Транспорт</NavLink>
              <NavLink to="/parking">Парковки</NavLink>
              <NavLink to="/utility">ЖКХ</NavLink>
              <NavLink to="/sensors">Датчики</NavLink>
              <NavLink to="/invoices">Счета</NavLink>
              <button className="link-button" onClick={onLogout} type="button">
                Выйти
              </button>
            </>
          ) : !loading ? (
            <>
              <NavLink to="/login">Вход</NavLink>
              <NavLink to="/register">Регистрация</NavLink>
            </>
          ) : null}
        </nav>
      </header>
      <main className="container">{children}</main>
    </>
  );
}

function AuthForm({ mode, onAuthenticated, sessionNotice }) {
  const navigate = useNavigate();
  const location = useLocation();
  const isLogin = mode === "login";
  const [form, setForm] = useState({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const activeRequest = useRef(0);
  const controller = useRef(null);
  const busy = useRef(false);
  useEffect(() => () => {
    activeRequest.current += 1;
    controller.current?.abort();
  }, []);

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    busy.current = true;
    const generation = ++activeRequest.current;
    controller.current = new AbortController();
    const signal = controller.current.signal;
    setError("");
    setSubmitting(true);
    try {
      if (isLogin) {
        const result = await apiFetch(API_URLS.identity, "/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: form.email, password: form.password }),
          signal,
        });
        if (signal.aborted || generation !== activeRequest.current) return;
        setToken(result.access_token);
        await onAuthenticated();
        if (signal.aborted || generation !== activeRequest.current) return;
        navigate(loginDestination(location.state?.returnTo), { replace: true });
      } else {
        await apiFetch(API_URLS.identity, "/auth/register", {
          method: "POST",
          body: JSON.stringify({
            email: form.email,
            password: form.password,
            first_name: form.first_name,
            last_name: form.last_name,
          }),
          signal,
        });
        if (signal.aborted || generation !== activeRequest.current) return;
        navigate("/login", { replace: true, state: location.state });
      }
    } catch (requestError) {
      if (!signal.aborted && generation === activeRequest.current) setError(requestError.message);
    } finally {
      busy.current = false;
      if (generation === activeRequest.current) setSubmitting(false);
    }
  }

  return (
    <section className="card form-card">
      <h1>{isLogin ? "Вход" : "Регистрация"}</h1>
      {isLogin && sessionNotice && <p role="status">{sessionNotice}</p>}
      <form onSubmit={submit}>
        {!isLogin && (
          <div className="form-row">
            <label>
              Имя
              <input name="first_name" onChange={updateField} required value={form.first_name} />
            </label>
            <label>
              Фамилия
              <input name="last_name" onChange={updateField} required value={form.last_name} />
            </label>
          </div>
        )}
        <label>
          Email
          <input name="email" onChange={updateField} required type="email" value={form.email} />
        </label>
        <label>
          Пароль
          <input
            minLength="8"
            name="password"
            onChange={updateField}
            required
            type="password"
            value={form.password}
          />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="button" disabled={submitting} type="submit">
          {submitting ? "Отправка..." : isLogin ? "Войти" : "Зарегистрироваться"}
        </button>
      </form>
      <p className="muted">
        {isLogin ? "Нет учётной записи? " : "Уже зарегистрированы? "}
        <Link to={isLogin ? "/register" : "/login"} state={location.state}>{isLogin ? "Регистрация" : "Войти"}</Link>
      </p>
    </section>
  );
}

function Profile({ currentUser }) {
  return (
    <section className="card">
      <h1>Профиль</h1>
      <dl className="profile-list">
        <div><dt>Имя</dt><dd>{currentUser.first_name}</dd></div>
        <div><dt>Фамилия</dt><dd>{currentUser.last_name}</dd></div>
        <div><dt>Email</dt><dd>{currentUser.email}</dd></div>
        <div><dt>Роль</dt><dd>{currentUser.role}</dd></div>
      </dl>
    </section>
  );
}

function ProtectedRoute({ currentUser, loading, error, onRetry, children }) {
  const location = useLocation();
  if (loading) return <p>Загрузка профиля...</p>;
  if (error) return <section className="card"><p className="error" role="alert">{error}</p><button className="button" onClick={onRetry}>Повторить</button></section>;
  return currentUser ? children : <Navigate replace to="/login" state={{ returnTo: location.pathname + location.search + location.hash }} />;
}

function NotFound() {
  return (
    <section className="card">
      <h1>Страница не найдена</h1>
      <Link to="/">Вернуться на главную</Link>
    </section>
  );
}

export default function App() {
  const location = useLocation();
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [profileError, setProfileError] = useState("");
  const [sessionNotice, setSessionNotice] = useState("");
  const request = useRef(0);
  const checkingSession = useRef(null);

  async function refreshProfile({ background = false } = {}) {
    const generation = ++request.current;
    const token = getToken();
    setProfileError("");
    if (!token) {
      setCurrentUser(null);
      setLoading(false);
      return;
    }
    if (!background) setLoading(true);
    try {
      const user = await apiFetch(API_URLS.identity, "/users/me");
      if (generation === request.current && token === getToken()) {
        setCurrentUser(user);
        setSessionNotice("");
      }
    } catch (error) {
      if (generation !== request.current || token !== getToken()) return;
      if (error.status === 401) {
        setToken(null);
        setCurrentUser(null);
        setSessionNotice("Сессия истекла или больше недействительна. Войдите снова, чтобы продолжить.");
      } else {
        setProfileError("Не удалось загрузить профиль. Сессия сохранена - повторите запрос.");
      }
      throw error;
    } finally {
      if (generation === request.current) setLoading(false);
    }
  }

  useEffect(() => {
    refreshProfile().catch(() => {});
    return () => { request.current += 1; };
  }, []);

  useEffect(() => {
    function authRejected(event) {
      const token = event.detail?.token;
      if (!token || token !== getToken() || checkingSession.current === token) return;
      checkingSession.current = token;
      refreshProfile({ background: true }).catch(() => {}).finally(() => {
        if (checkingSession.current === token) checkingSession.current = null;
      });
    }
    window.addEventListener(AUTH_REJECTED_EVENT, authRejected);
    return () => window.removeEventListener(AUTH_REJECTED_EVENT, authRejected);
  }, []);

  useEffect(() => {
    function sessionChanged(event) {
      if (event.key !== "access_token" && event.key !== null) return;
      request.current += 1;
      setCurrentUser(null); // Unmount private pages and discard their cached data.
      refreshProfile().catch(() => {});
    }
    window.addEventListener("storage", sessionChanged);
    return () => window.removeEventListener("storage", sessionChanged);
  }, []);

  function logout() {
    request.current += 1;
    setToken(null);
    setCurrentUser(null);
    setProfileError("");
    setSessionNotice("");
    setLoading(false);
  }

  function protect(children) {
    return <ProtectedRoute currentUser={currentUser} loading={loading} error={profileError} onRetry={() => refreshProfile().catch(() => {})}>{children}</ProtectedRoute>;
  }

  return (
    <Layout currentUser={currentUser} loading={loading} onLogout={logout}>
      <Routes>
        <Route path="/" element={<HomePage key={currentUser?.id ?? "guest"} currentUser={currentUser} loading={loading} profileError={profileError} sessionNotice={sessionNotice} onRetry={() => refreshProfile().catch(() => {})} />} />
        <Route
          path="/login"
          element={currentUser ? <Navigate replace to={loginDestination(location.state?.returnTo)} /> : <AuthForm key="login" mode="login" onAuthenticated={refreshProfile} sessionNotice={sessionNotice} />}
        />
        <Route
          path="/register"
          element={currentUser ? <Navigate replace to={loginDestination(location.state?.returnTo)} /> : <AuthForm key="register" mode="register" onAuthenticated={refreshProfile} />}
        />
        <Route
          path="/profile"
          element={protect(<Profile currentUser={currentUser} />)}
        />
        <Route path="/users" element={protect(<UsersPage />)} />
        <Route path="/transport" element={protect(<TransportPage />)} />
        <Route path="/parking" element={protect(<ParkingPage currentUser={currentUser} />)} />
        <Route path="/utility" element={protect(<UtilityIssuesPage currentUser={currentUser} />)} />
        <Route path="/sensors" element={protect(<SensorsPage />)} />
        <Route path="/invoices" element={protect(<InvoicesPage currentUser={currentUser} />)} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
