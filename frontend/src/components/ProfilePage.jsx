import { ApiError, changePassword, fetchProfile } from "../api";
import Header from "./Header";

const { useEffect, useState } = React;

const ACTION_LABEL = {
  visit_page: "Открытие страницы",
  use_test_dataset: "Тестовый набор",
  use_custom_sources: "Свои источники",
  use_custom_text: "Свой текст",
  use_firecrawl: "Firecrawl",
  use_external_fetch: "Внешний обход",
  generate_digest: "Дайджест",
  export_digest: "Экспорт",
  save_digest: "Сохранение дайджеста",
  login_success: "Вход",
  login_fail: "Неудачный вход",
  logout: "Выход",
  register_success: "Регистрация",
  profile_opened: "Профиль",
  admin_view: "Открытие админки",
  auth_required: "Запрос авторизации",
  error_event: "Ошибка",
};

const NO_DATA = "—";

function parseDate(value) {
  if (value == null) return null;
  const raw = String(value).trim();
  if (!raw) return null;
  let normalized = raw;
  if (/^\d{4}-\d{2}-\d{2}[ T]/.test(normalized)) {
    normalized = normalized.replace(" ", "T");
    if (!/[zZ]|[+\-]\d\d:?\d\d$/.test(normalized)) normalized += "Z";
  }
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return null;
  return date;
}

function fmt(value) {
  const date = parseDate(value);
  if (!date) return NO_DATA;
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function fmtDate(value) {
  const date = parseDate(value);
  if (!date) return NO_DATA;
  return date.toLocaleDateString("ru-RU");
}

const WEEKDAY_RU = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];

function weekdayLabel(iso) {
  const date = parseDate(iso + "T00:00:00Z");
  if (!date) return "";
  return WEEKDAY_RU[date.getUTCDay()] || "";
}

function pluralDays(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "день";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "дня";
  return "дней";
}

function StreakBlock({ streak }) {
  if (!streak) return null;
  const { current = 0, best = 0, activeToday = false, days = [] } = streak;

  let subtitle;
  if (activeToday) {
    subtitle = "Сегодня активность засчитана.";
  } else if (current > 0) {
    subtitle = "Запустите анализ сегодня, чтобы сохранить серию.";
  } else {
    subtitle = "Запустите тестовый набор или анализ, чтобы начать серию.";
  }

  const hot = current >= 7;
  const warm = current >= 3;

  return (
    <section className={`pp-streak ${warm ? "is-warm" : ""} ${hot ? "is-hot" : ""}`}>
      <div className="pp-streak-head">
        <span className="pp-block-label">Day streak</span>
        {hot && <span className="pp-streak-badge">горячая серия</span>}
      </div>

      <div className="pp-streak-main">
        <div className="pp-streak-current">
          <span className="pp-streak-number">{current}</span>
          <span className="pp-streak-unit">{pluralDays(current)}</span>
        </div>
        <div className="pp-streak-best">
          <span className="pp-block-sublabel">Лучший</span>
          <b>{best}</b>
        </div>
      </div>

      <div className="pp-streak-strip" role="list" aria-label="Активность за неделю">
        {days.map((d) => (
          <div
            key={d.date}
            role="listitem"
            className={
              "pp-streak-day" +
              (d.active ? " is-active" : "") +
              (d.isToday ? " is-today" : "")
            }
            title={`${d.date}${d.active ? ` · ${d.count} действ.` : " · без активности"}`}
          >
            <span className="pp-streak-mark" aria-hidden="true">{d.active ? "▪" : "·"}</span>
            <span className="pp-streak-label">
              {d.isToday ? "сегодня" : weekdayLabel(d.date)}
            </span>
          </div>
        ))}
      </div>

      <div className="pp-streak-subtitle">{subtitle}</div>
    </section>
  );
}

export default function ProfilePage({ currentUser, authChecked, onLogout, onRequireLogin, authBadge }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pwOpen, setPwOpen] = useState(false);
  const [pwOld, setPwOld] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwError, setPwError] = useState("");
  const [pwOk, setPwOk] = useState(false);
  const [pwLoading, setPwLoading] = useState(false);

  useEffect(() => {
    if (!authChecked) return;
    if (!currentUser) {
      setLoading(false);
      return;
    }
    let mounted = true;
    setLoading(true);
    setError("");
    fetchProfile()
      .then((res) => { if (mounted) setData(res); })
      .catch((err) => { if (mounted) setError(err?.message || "Не удалось загрузить профиль."); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [authChecked, currentUser?.username]);

  if (authChecked && !currentUser) {
    return (
      <div className="app-shell">
        <Header authBadge={authBadge} variant="page" />
        <main className="profile-page">
          <div className="profile-page-inner">
            <a className="pp-back" href="/">← На главную</a>
            <h1 className="pp-title">Профиль</h1>
            <div className="pp-error-box">
              Для доступа к профилю войдите или создайте аккаунт.
            </div>
            <div className="pp-action-grid">
              <button
                type="button"
                className="pp-action pp-action-primary"
                onClick={() => onRequireLogin?.("Войдите, чтобы открыть профиль.")}
              >
                Войти
              </button>
              <a className="pp-action" href="/">На главную</a>
            </div>
          </div>
        </main>
      </div>
    );
  }

  async function submitPassword(e) {
    e.preventDefault();
    setPwError("");
    setPwOk(false);
    if (pwNew.length < 6) { setPwError("Пароль должен быть не короче 6 символов."); return; }
    setPwLoading(true);
    try {
      await changePassword(pwOld, pwNew);
      setPwOk(true);
      setPwOld(""); setPwNew("");
    } catch (err) {
      if (err instanceof ApiError && err.code === "INVALID_CREDENTIALS") {
        setPwError("Неверный текущий пароль.");
      } else if (err?.code === "WEAK_PASSWORD") {
        setPwError("Пароль должен быть не короче 6 символов.");
      } else {
        setPwError(err?.message || "Не удалось сменить пароль.");
      }
    } finally { setPwLoading(false); }
  }

  function goAdmin() {
    if (typeof window !== "undefined") window.location.href = "/admin";
  }

  const user = data?.user || currentUser || {};
  const stats = data?.stats || {};
  const streak = data?.streak || null;
  const events = data?.recentEvents || [];
  const isAdmin = user.role === "admin";

  return (
    <div className="app-shell">
      <Header authBadge={authBadge} variant="page" />
      <main className="profile-page">
        <div className="profile-page-inner">
          <a className="pp-back" href="/">← На главную</a>

          <section className="pp-head">
            <div className="pp-avatar">{(user.username || "?").slice(0, 1).toUpperCase()}</div>
            <div className="pp-head-text">
              <h1 className="pp-name">
                <span className="pp-name-text">{user.username || NO_DATA}</span>
                {isAdmin && <span className="pp-admin-badge">ADMIN</span>}
              </h1>
              <div className="pp-role">{isAdmin ? "Администратор" : "Пользователь"}</div>
              <div className="pp-access">Полный доступ</div>
            </div>
            <div className="pp-head-tools">
              <div className="pp-head-tools-row">
                {isAdmin && (
                  <button type="button" className="pp-tool-btn" onClick={goAdmin}>
                    Админ-панель
                  </button>
                )}
                <button
                  type="button"
                  className={`pp-tool-btn ${pwOpen ? "is-active" : ""}`}
                  onClick={() => setPwOpen((v) => !v)}
                >
                  Сменить пароль
                </button>
              </div>
            </div>
          </section>

          {loading && (
            <div className="pp-loading">Загружаем профиль…</div>
          )}

          {error && !loading && (
            <div className="pp-error-box">{error}</div>
          )}

          {!loading && !error && (
            <>
              <section className="pp-meta">
                <div className="pp-meta-cell">
                  <span className="pp-block-label">Регистрация</span>
                  <span className="pp-meta-value">{fmtDate(user.created_at)}</span>
                </div>
                <div className="pp-meta-cell">
                  <span className="pp-block-label">Последний вход</span>
                  <span className="pp-meta-value">{fmt(user.last_login_at)}</span>
                </div>
              </section>

              <StreakBlock streak={streak} />

              <section className="pp-stats">
                <div className="pp-stat">
                  <span className="pp-stat-value">{stats.testRuns ?? 0}</span>
                  <span className="pp-stat-label">тестовый набор</span>
                </div>
                <div className="pp-stat">
                  <span className="pp-stat-value">{stats.customRuns ?? 0}</span>
                  <span className="pp-stat-label">свои источники</span>
                </div>
                <div className="pp-stat">
                  <span className="pp-stat-value">{stats.digestGenerations ?? 0}</span>
                  <span className="pp-stat-label">дайджестов</span>
                </div>
                <div className="pp-stat">
                  <span className="pp-stat-value">{stats.savedDigests ?? 0}</span>
                  <span className="pp-stat-label">сохранено</span>
                </div>
              </section>

              <section className="pp-events-section">
                <div className="pp-section-heading">
                  <span className="pp-block-label">Последние действия</span>
                  <span className="pp-section-count">{events.length}</span>
                </div>
                <ul className="pp-events">
                  {events.length === 0 && (
                    <li className="pp-events-empty">Пока пусто.</li>
                  )}
                  {events.map((ev, idx) => (
                    <li key={idx} className={`pp-event status-${ev.status || "ok"}`}>
                      <span className="pp-event-action">
                        {ACTION_LABEL[ev.action] || ev.action || NO_DATA}
                      </span>
                      <span className="pp-event-time">{fmt(ev.created_at)}</span>
                    </li>
                  ))}
                </ul>
              </section>

              {pwOpen && (
                <form className="pp-pw" onSubmit={submitPassword}>
                  <div className="pp-section-heading">
                    <span className="pp-block-label">Смена пароля</span>
                  </div>
                  <input
                    type="password"
                    placeholder="Текущий пароль"
                    value={pwOld}
                    onChange={(e) => setPwOld(e.target.value)}
                    autoComplete="current-password"
                    disabled={pwLoading}
                  />
                  <input
                    type="password"
                    placeholder="Новый пароль (мин. 6)"
                    value={pwNew}
                    onChange={(e) => setPwNew(e.target.value)}
                    autoComplete="new-password"
                    disabled={pwLoading}
                  />
                  {pwError && <div className="pp-pw-error">{pwError}</div>}
                  {pwOk && <div className="pp-pw-ok">Пароль обновлён.</div>}
                  <div className="pp-pw-actions">
                    <button
                      type="button"
                      className="pp-action"
                      onClick={() => { setPwOpen(false); setPwError(""); }}
                      disabled={pwLoading}
                    >
                      Отмена
                    </button>
                    <button type="submit" className="pp-action pp-action-primary" disabled={pwLoading}>
                      {pwLoading ? "Сохраняем…" : "Сменить"}
                    </button>
                  </div>
                </form>
              )}

              <section className="pp-logout-section">
                <button
                  type="button"
                  className="pp-action pp-action-logout"
                  onClick={onLogout}
                >
                  Выйти из профиля
                </button>
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
