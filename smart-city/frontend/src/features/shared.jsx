import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "../api.js";

export function useApiList(baseUrl, path) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const request = useRef(null);
  const reload = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    if (!path) {
      setData([]);
      setLoading(false);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await apiFetch(baseUrl, path, { signal: controller.signal });
      if (!controller.signal.aborted) setData(result);
    } catch (e) {
      if (!controller.signal.aborted) setError(e.status ? e.message : "Сервис недоступен. Попробуйте ещё раз.");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [baseUrl, path]);
  useEffect(() => {
    setData([]);
    reload();
    return () => request.current?.abort();
  }, [reload]);
  return { data, loading, error, reload };
}

export function useAction() {
  const busy = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function run(action, success) {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setError("");
    setMessage("");
    try {
      const result = await action();
      setMessage(typeof success === "function" ? success(result) : success);
    } catch (e) {
      setError(e.status ? e.message : "Сеть недоступна. Результат запроса неизвестен; попробуйте повторить действие.");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }
  return { pending, error, message, run };
}

export function ListStatus({ list, empty }) {
  return <>
    {list.loading && <p role="status">Загрузка...</p>}
    {list.error && <p className="error" role="alert">{list.error}</p>}
    {!list.loading && !list.error && !list.data.length && <p>{empty}</p>}
    <button className="button secondary" disabled={list.loading} onClick={list.reload}>Обновить</button>
  </>;
}

export function ActionStatus({ action }) {
  return <>
    {action.pending && <p role="status">Выполняется...</p>}
    {action.error && <p className="error" role="alert">{action.error}</p>}
    {action.message && <p role="status">{action.message}</p>}
  </>;
}

export function time(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

export function pendingOperation(storageKey) {
  try { return JSON.parse(sessionStorage.getItem(storageKey)); }
  catch { return null; }
}

export async function postOperation(baseUrl, path, storageKey, payload) {
  const body = payload === undefined ? null : JSON.stringify(payload);
  let attempt = pendingOperation(storageKey);
  const hadPending = Boolean(attempt);
  if (attempt && attempt.body !== body) {
    const error = new Error("Сначала подтвердите предыдущую операцию с исходными данными.");
    error.status = 409;
    throw error;
  }
  if (!attempt) attempt = { key: crypto.randomUUID(), body };
  sessionStorage.setItem(storageKey, JSON.stringify(attempt));
  try {
    const result = await apiFetch(baseUrl, path, {
      method: "POST",
      headers: { "X-Idempotency-Key": attempt.key },
      ...(body === null ? {} : { body }),
    });
    sessionStorage.removeItem(storageKey);
    return result;
  } catch (error) {
    // A first, explicitly rejected request did not commit. It is safe to edit.
    // A prior unknown outcome must retain its key, even if a later retry is 401.
    if (!hadPending && error.status >= 400 && error.status < 500) sessionStorage.removeItem(storageKey);
    throw error;
  }
}
