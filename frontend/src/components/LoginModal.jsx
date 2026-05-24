import { ApiError, login, register } from "../api";

const { useEffect, useRef, useState } = React;

const TAB_LOGIN = "login";
const TAB_REGISTER = "register";

export default function LoginModal({ open, reason, initialTab, onClose, onSuccess }) {
  const [tab, setTab] = useState(initialTab === TAB_REGISTER ? TAB_REGISTER : TAB_LOGIN);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const usernameRef = useRef(null);

  useEffect(() => {
    if (open) {
      setTab(initialTab === TAB_REGISTER ? TAB_REGISTER : TAB_LOGIN);
      setError("");
      setPassword("");
      setTimeout(() => usernameRef.current?.focus(), 50);
    }
  }, [open, initialTab]);

  useEffect(() => { setError(""); }, [tab]);

  if (!open) return null;

  async function handleSubmit(event) {
    event.preventDefault();
    const u = username.trim();

    if (!u || !password) {
      setError("Введите логин и пароль.");
      return;
    }

    if (tab === TAB_REGISTER && password.length < 6) {
      setError("Пароль должен быть не короче 6 символов.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const data = tab === TAB_REGISTER
        ? await register(u, password)
        : await login(u, password);
      onSuccess?.(data?.user);
    } catch (err) {
      if (err instanceof ApiError || err?.code) {
        if (err.code === "USER_EXISTS") {
          setError("Пользователь уже существует. Войдите вместо регистрации.");
        } else if (err.code === "INVALID_CREDENTIALS") {
          setError("Неверный логин или пароль.");
        } else if (err.code === "WEAK_PASSWORD") {
          setError("Пароль должен быть не короче 6 символов.");
        } else if (err.code === "INVALID_USERNAME") {
          setError("Логин: 3–32 символа, латиница, цифры, _ . -");
        } else if (err.code === "RATE_LIMITED") {
          setError("Слишком много попыток. Попробуйте позже.");
        } else if (err.code === "NETWORK_ERROR") {
          setError("Не удалось подключиться к серверу.");
        } else {
          setError(err.message || "Не удалось выполнить запрос.");
        }
      } else {
        setError("Не удалось подключиться к серверу.");
      }
    } finally {
      setLoading(false);
    }
  }

  const submitLabel = tab === TAB_REGISTER
    ? (loading ? "Создаём аккаунт…" : "Создать аккаунт")
    : (loading ? "Входим…" : "Войти");

  return (
    <div className="auth-modal-backdrop" role="dialog" aria-modal="true">
      <div className="auth-modal">
        <div className="auth-modal-head">
          <div className="auth-modal-title">Вход в TrendWatcher</div>
          <button
            type="button"
            className="auth-modal-close"
            onClick={onClose}
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>

        {reason && <div className="auth-modal-reason">{reason}</div>}

        <div className="auth-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === TAB_LOGIN}
            className={`auth-tab ${tab === TAB_LOGIN ? "is-active" : ""}`}
            onClick={() => setTab(TAB_LOGIN)}
          >
            Вход
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === TAB_REGISTER}
            className={`auth-tab ${tab === TAB_REGISTER ? "is-active" : ""}`}
            onClick={() => setTab(TAB_REGISTER)}
          >
            Регистрация
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-field">
            <span>Логин</span>
            <input
              ref={usernameRef}
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
            />
          </label>
          <label className="auth-field">
            <span>Пароль{tab === TAB_REGISTER ? " (мин. 6 символов)" : ""}</span>
            <input
              type="password"
              autoComplete={tab === TAB_REGISTER ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
            />
          </label>

          {error && <div className="auth-error">{error}</div>}

          <div className="auth-actions">
            <button type="button" className="secondary-button" onClick={onClose} disabled={loading}>
              Отмена
            </button>
            <button type="submit" className="primary-button" disabled={loading}>
              {submitLabel}
            </button>
          </div>
        </form>

        <div className="auth-hint">
          Тестовый набор доступен без входа. Аккаунт нужен, чтобы анализировать
          свои источники: тексты, ссылки, Firecrawl и live-режим.
        </div>
      </div>
    </div>
  );
}
