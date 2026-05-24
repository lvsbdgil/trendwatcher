const { useState } = React;

const PRESETS = [
  { label: "Финтех-новости", query: "финтех новости банки платежи за последнюю неделю" },
  { label: "BNPL и рассрочки", query: "BNPL рассрочка банки сервисы Россия новости" },
  { label: "Цифровой рубль", query: "цифровой рубль ЦБ запуск внедрение банки" },
  { label: "Регулирование ЦБ", query: "Банк России регулирование финтех банки изменения требования" },
];

function LockedFirecrawlAction({ onLogin }) {
  return (
    <button
      type="button"
      className="primary-button is-locked"
      onClick={onLogin}
      title="Доступно после входа"
      aria-label="Войдите, чтобы использовать"
    >
      <span className="lock-mark" aria-hidden="true">[locked]</span>
      <span>Войдите, чтобы использовать</span>
    </button>
  );
}

export default function FirecrawlPanel({ loading, onCrawl, onSearch, isGuest = false, onLogin }) {
  const [mode, setMode] = useState("search");
  const [query, setQuery] = useState("");
  const [searchLimit, setSearchLimit] = useState(10);
  const [crawlUrls, setCrawlUrls] = useState("");
  const [crawlLimit, setCrawlLimit] = useState(15);

  function handleSearch() {
    if (!query.trim()) return;
    onSearch(query.trim(), searchLimit);
  }

  function handlePreset(preset) {
    if (isGuest) {
      onLogin?.();
      return;
    }
    setQuery(preset.query);
    onSearch(preset.query, searchLimit);
  }

  function handleCrawl() {
    const urls = crawlUrls.split("\n").map((u) => u.trim()).filter(Boolean);
    if (!urls.length) return;
    onCrawl(urls, crawlLimit);
  }

  return (
    <div className="firecrawl-panel">
      <div className="firecrawl-tabs">
        <button
          type="button"
          className={mode === "search" ? "is-active" : ""}
          onClick={() => setMode("search")}
        >
          Поиск по запросу
        </button>
        <button
          type="button"
          className={mode === "crawl" ? "is-active" : ""}
          onClick={() => setMode("crawl")}
        >
          Обход источника
        </button>
      </div>

      {mode === "search" && (
        <>
          <div className="firecrawl-header">
            <span className="lbl">Поиск Firecrawl</span>
            <p>Firecrawl найдёт страницы по запросу и передаст публикации на анализ.</p>
          </div>
          <div className="preset-chips">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className="preset-chip"
                disabled={loading}
                onClick={() => handlePreset(p)}
              >
                {p.label}
              </button>
            ))}
          </div>

          <input
            className="url-input"
            type="text"
            placeholder="финтех тренды банки BNPL"
            value={query}
            disabled={loading}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <div className="firecrawl-controls">
            <label className="select-control">
              Результатов
              <select
                value={searchLimit}
                disabled={loading || isGuest}
                onChange={(e) => setSearchLimit(Number(e.target.value))}
              >
                {[5, 10, 15, 20].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </label>
            {isGuest ? (
              <LockedFirecrawlAction
                label="Найти и собрать"
                hint="Авторизуйтесь, чтобы запустить поиск Firecrawl"
                onLogin={onLogin}
              />
            ) : (
              <button
                className="primary-button"
                disabled={loading || !query.trim()}
                onClick={handleSearch}
              >
                {loading ? "Ищем..." : "Найти и собрать"}
              </button>
            )}
          </div>
        </>
      )}

      {mode === "crawl" && (
        <>
          <div className="firecrawl-header">
            <span className="lbl">Обход источника</span>
            <p>Укажите URL источников. Firecrawl соберёт публикации с найденных страниц.</p>
          </div>
          <textarea
            className="url-textarea"
            placeholder={"https://habr.com/ru/hub/fintech/\nhttps://example.com/news/"}
            value={crawlUrls}
            rows={4}
            disabled={loading}
            onChange={(e) => setCrawlUrls(e.target.value)}
          />
          <div className="firecrawl-controls">
            <label className="select-control">
              Глубина
              <select
                value={crawlLimit}
                disabled={loading}
                onChange={(e) => setCrawlLimit(Number(e.target.value))}
              >
                {[5, 10, 15, 20, 30].map((v) => (
                  <option key={v} value={v}>{v} страниц</option>
                ))}
              </select>
            </label>
            {isGuest ? (
              <LockedFirecrawlAction
                label="Собрать публикации"
                hint="Авторизуйтесь, чтобы обходить источники через Firecrawl"
                onLogin={onLogin}
              />
            ) : (
              <button
                className="primary-button"
                disabled={loading || !crawlUrls.trim()}
                onClick={handleCrawl}
              >
                {loading ? "Собираем..." : "Собрать публикации"}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
