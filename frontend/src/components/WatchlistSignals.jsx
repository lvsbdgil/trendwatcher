import { filterSignalsByWatchlist, topicLabel } from "../utils/watchlist";

const { useMemo } = React;

function formatHotness(h) {
  if (h == null) return null;
  const num = Number(h);
  if (Number.isNaN(num)) return null;
  return Math.round(num);
}

function formatConfidence(c) {
  if (c == null) return null;
  const num = Number(c);
  if (Number.isNaN(num)) return null;
  return Math.round(num * 100);
}

function pluralSignals(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "сигнал";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "сигнала";
  return "сигналов";
}

function pluralTopics(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "теме";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "темам";
  return "темам";
}

export default function WatchlistSignals({ signals, selectedTopics }) {
  const result = useMemo(
    () => filterSignalsByWatchlist(signals, selectedTopics),
    [signals, selectedTopics],
  );

  if (!selectedTopics || selectedTopics.length === 0) {
    return (
      <section className="watchlist-signals">
        <div className="section-heading">
          <p>Сигналы по вашим темам</p>
          <span>Watchlist пуст</span>
        </div>
        <div className="watchlist-empty">
          Watchlist пуст. Отметьте темы в блоке «Watchlist» выше,
          чтобы здесь появилась подборка релевантных сигналов.
        </div>
      </section>
    );
  }

  const { signals: matched, matchedCount, selectedCount } = result;

  return (
    <section className="watchlist-signals">
      <div className="section-heading">
        <p>Сигналы по вашим темам</p>
        <span>
          {matchedCount > 0
            ? `${matchedCount} ${pluralSignals(matchedCount)} по ${selectedCount} ${pluralTopics(selectedCount)}`
            : "0 совпадений"}
        </span>
      </div>

      {matchedCount === 0 ? (
        <div className="watchlist-empty">
          По выбранным темам сигналов не найдено. Можно расширить watchlist
          или запустить анализ на большем наборе источников.
        </div>
      ) : (
        <div className="watchlist-list">
          {matched.map((signal, index) => {
            const hotness = formatHotness(signal.hotness);
            const confidence = formatConfidence(signal.confidence);
            const firstSource = Array.isArray(signal.sources) ? signal.sources[0] : null;
            const whyNow = signal.why_now || signal.whyNow || "";
            const title = signal.headline || signal.title || "—";

            return (
              <article
                className="watchlist-signal-card"
                key={`${title}-${index}`}
              >
                <h4 className="watchlist-signal-title">{title}</h4>

                {(hotness != null || confidence != null) && (
                  <div className="watchlist-signal-metrics">
                    {hotness != null && (
                      <span className="watchlist-metric">
                        <span className="watchlist-metric-k">hotness</span>
                        <span className="watchlist-metric-v">{hotness}</span>
                      </span>
                    )}
                    {confidence != null && (
                      <span className="watchlist-metric">
                        <span className="watchlist-metric-k">confidence</span>
                        <span className="watchlist-metric-v">{confidence}%</span>
                      </span>
                    )}
                  </div>
                )}

                <div className="watchlist-signal-topics">
                  {signal.category && (
                    <span className="watchlist-category-chip">{signal.category}</span>
                  )}
                  {signal.matchedTopics.map((id) => (
                    <span key={id} className="watchlist-topic-chip">
                      {topicLabel(id)}
                    </span>
                  ))}
                </div>

                {whyNow && (
                  <p className="watchlist-signal-why">
                    <span className="watchlist-signal-why-k">why now</span>
                    {whyNow}
                  </p>
                )}

                {firstSource?.url && (
                  <a
                    className="watchlist-signal-source"
                    href={firstSource.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {firstSource.url}
                  </a>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
