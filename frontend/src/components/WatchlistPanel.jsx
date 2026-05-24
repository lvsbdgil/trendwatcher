import { WATCHLIST_TOPICS } from "../utils/watchlist";

export default function WatchlistPanel({ selectedTopics, onChange }) {
  const selected = Array.isArray(selectedTopics) ? selectedTopics : [];
  const selectedSet = new Set(selected);

  function toggle(id) {
    if (selectedSet.has(id)) {
      onChange(selected.filter((t) => t !== id));
    } else {
      onChange([...selected, id]);
    }
  }

  function selectAll() {
    onChange(WATCHLIST_TOPICS.map((t) => t.id));
  }

  function reset() {
    onChange([]);
  }

  const count = selected.length;

  return (
    <div className="watchlist-panel">
      <div className="watchlist-head">
        <div className="watchlist-head-text">
          <div className="watchlist-title">Watchlist</div>
          <div className="watchlist-subtitle">
            Выберите темы, по которым нужно отдельно подсветить сигналы после анализа.
          </div>
        </div>
        <div className="watchlist-actions">
          <button
            type="button"
            className="watchlist-action-link"
            onClick={selectAll}
            disabled={count === WATCHLIST_TOPICS.length}
          >
            Выбрать всё
          </button>
          <span className="watchlist-action-sep">·</span>
          <button
            type="button"
            className="watchlist-action-link"
            onClick={reset}
            disabled={count === 0}
          >
            Сбросить
          </button>
        </div>
      </div>

      <div className="watchlist-chip-grid" role="group" aria-label="Темы Watchlist">
        {WATCHLIST_TOPICS.map((topic) => {
          const isActive = selectedSet.has(topic.id);
          return (
            <button
              key={topic.id}
              type="button"
              className={`watchlist-chip ${isActive ? "is-active" : ""}`}
              aria-pressed={isActive}
              onClick={() => toggle(topic.id)}
            >
              <span className="watchlist-chip-dot" aria-hidden="true" />
              <span className="watchlist-chip-label">{topic.label}</span>
            </button>
          );
        })}
      </div>

      <div className="watchlist-counter">
        выбрано {count} {pluralTopics(count)}
      </div>
    </div>
  );
}

function pluralTopics(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "тема";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "темы";
  return "тем";
}
