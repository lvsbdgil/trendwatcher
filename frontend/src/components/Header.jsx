function scrollToTop() {
  if (typeof window === "undefined") return;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function isHome() {
  if (typeof window === "undefined") return true;
  const path = window.location.pathname.replace(/\/+$/, "");
  return path === "" || path === "/";
}

function handleBrandClick(event) {
  if (isHome()) {
    event.preventDefault();
    scrollToTop();
  }
}

export default function Header({ authBadge, variant = "home" }) {
  const onHome = variant === "home";

  return (
    <>
      <header className="ab-top" id="top">
        <a
          href="/"
          className="brand brand-button"
          onClick={handleBrandClick}
          aria-label={onHome ? "Наверх" : "На главную"}
          title={onHome ? "Наверх" : "На главную"}
        >
          <img
            src="/logo.svg"
            alt=""
            className="brand-logo"
            width="32"
            height="32"
            onError={(e) => { e.currentTarget.style.display = "none"; }}
          />
          <span className="brand-text">BigPuzoTeam</span>
        </a>
        <div className="meta">
          {authBadge}
        </div>
      </header>

      {onHome && (
        <section className="hero" id="summary">
          <div className="wrap">
            <div className="eyebrow">Внутренний мониторинг</div>
            <h1 className="hero-display">
              TrendWatcher
            </h1>
            <p className="hero-sub">
              Инструмент помогает быстро разобрать публикации, убрать шум и дубли,
              показать важные сигналы и собрать короткий дайджест для продуктовой команды банка.
            </p>

            <div className="hero-strip">
              <div>
                <div className="k">вход</div>
                <div className="v">URL<small>ссылки, текст или CSV</small></div>
              </div>
              <div>
                <div className="k">очистка</div>
                <div className="v">шум<small>нерелевантные материалы отдельно</small></div>
              </div>
              <div>
                <div className="k">оценка</div>
                <div className="v">важность<small>факторы объясняются в карточке</small></div>
              </div>
              <div>
                <div className="k">итог</div>
                <div className="v">дайджест<small>вывод для команды</small></div>
              </div>
            </div>
          </div>
        </section>
      )}
    </>
  );
}
