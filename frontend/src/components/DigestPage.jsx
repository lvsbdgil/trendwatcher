import Header from "./Header";
import DigestPanel from "./DigestPanel";
import ExportCenter, { ExportActions } from "./ExportCenter";
import QualityPanel from "./QualityPanel";
import { translateRejectReason } from "../utils/translateReason";
import {
  digestMetrics,
  duplicateRows,
  noEvidenceRows,
} from "../utils/resultMetrics";

const { useEffect, useMemo, useState } = React;

function safeTitle(item) {
  return String(item?.title || item?.headline || item?.kept || "Материал без заголовка").trim();
}

function sourceLine(item) {
  const source = item?.source || item?.url || item?.primary_source_url || "";
  if (typeof source === "string") return source;
  return source?.name || source?.url || "";
}

function reasonLine(item) {
  return translateRejectReason(item?.rejection_reason || item?.reject_reason || item?.reason || "не прошел фильтр качества");
}

function MiniMetric({ label, value }) {
  return (
    <div className="digest-stat">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function ReviewListCard({ title, meta, items, emptyText, renderItem }) {
  return (
    <section className="digest-review-card">
      <div className="section-heading">
        <p>{title}</p>
        <span>{meta}</span>
      </div>
      {items.length > 0 ? (
        <div className="digest-review-list">
          {items.slice(0, 6).map((item, index) => (
            <article className="digest-review-item" key={item.id || `${safeTitle(item)}-${index}`}>
              {renderItem(item, index)}
            </article>
          ))}
        </div>
      ) : (
        <div className="digest-card-empty">{emptyText}</div>
      )}
    </section>
  );
}

function FullDigestModal({
  open,
  onClose,
  result,
  signals,
  digest,
  status,
  currentUser,
  selectedWatchlistTopics,
  onTrackEvent,
}) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    document.body.classList.add("modal-open");
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.classList.remove("modal-open");
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="digest-modal-backdrop" role="presentation">
      <section className="digest-modal" role="dialog" aria-modal="true" aria-labelledby="full-digest-title">
        <header className="digest-modal-head">
          <div>
            <div className="export-format-chip">полный текст</div>
            <h2 id="full-digest-title">Полный дайджест</h2>
          </div>
          <button type="button" className="digest-modal-close" onClick={onClose}>
            Закрыть
          </button>
        </header>

        <div className="digest-modal-body">
          <DigestPanel
            digest={digest}
            status={status}
            className="digest-modal-panel"
            showDownload={false}
          />
        </div>

        <footer className="digest-modal-actions">
          <ExportActions
            result={result}
            signals={signals}
            digest={digest}
            currentUser={currentUser}
            selectedWatchlistTopics={selectedWatchlistTopics}
            onTrackEvent={onTrackEvent}
            compact
          />
        </footer>
      </section>
    </div>
  );
}

export default function DigestPage({
  authBadge,
  result,
  signals = [],
  rejectedRows = [],
  status = "idle",
  currentUser,
  selectedWatchlistTopics = [],
  onTrackEvent,
  onBack,
}) {
  const [fullOpen, setFullOpen] = useState(false);
  const metrics = useMemo(
    () => digestMetrics(result, signals, rejectedRows, selectedWatchlistTopics),
    [result, signals, rejectedRows, selectedWatchlistTopics],
  );
  const duplicates = useMemo(() => duplicateRows(result, signals), [result, signals]);
  const withoutEvidence = useMemo(
    () => noEvidenceRows(result, signals, rejectedRows),
    [result, signals, rejectedRows],
  );

  const hasResult = Boolean(result);
  const digest = result?.digest || "";
  const digestStatus = hasResult ? status : "idle";

  if (!hasResult) {
    return (
      <div className="app-shell digest-route-shell">
        <Header authBadge={authBadge} variant="page" />
        <main className="layout digest-route-layout">
          <section className="digest-empty-page">
            <div className="export-format-chip">digest</div>
            <h1>Сначала запустите анализ</h1>
            <p>Итоговый дайджест, контроль качества и экспорт появятся здесь после обработки материалов.</p>
            <button type="button" className="secondary-button" onClick={onBack}>
              Назад к анализу
            </button>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell digest-route-shell">
      <Header authBadge={authBadge} variant="page" />
      <main className="layout digest-route-layout">
        <header className="digest-page-head">
          <div>
            <button type="button" className="digest-back-button" onClick={onBack}>
              ← На главную
            </button>
            <h1>Итоговый дайджест</h1>
            <p>Собранные сигналы, контроль качества и экспорт результата для команды</p>
          </div>
          <div className="digest-stats-grid" aria-label="Метрики дайджеста">
            <MiniMetric label="выбранные сигналы" value={metrics.signalCount} />
            <MiniMetric label="watchlist" value={metrics.watchlistCount} />
            <MiniMetric label="дубли" value={metrics.duplicatesCount} />
            <MiniMetric label="шум" value={metrics.noiseCount} />
            <MiniMetric label="без evidence" value={metrics.noEvidenceCount} />
          </div>
        </header>

        <div className="digest-layout">
          <div className="digest-left">
            <QualityPanel
              result={result}
              signals={signals}
              rejectedRows={rejectedRows}
              loading={false}
            />

            <ReviewListCard
              title="Материалы, отброшенные как шум"
              meta={`${rejectedRows.length} материалов`}
              items={rejectedRows}
              emptyText="Нерелевантные материалы не найдены"
              renderItem={(item, index) => (
                <>
                  <div className="digest-review-kicker">noise #{String(index + 1).padStart(2, "0")}</div>
                  <h3>{safeTitle(item)}</h3>
                  <p>{reasonLine(item)}</p>
                  {sourceLine(item) && <span>{sourceLine(item)}</span>}
                </>
              )}
            />

            <ReviewListCard
              title="Дубли / перепечатки"
              meta={`${metrics.duplicatesCount} найдено`}
              items={duplicates}
              emptyText="Дубли не обнаружены"
              renderItem={(item) => (
                <>
                  <div className="digest-review-kicker">duplicate</div>
                  <h3>{item.kept}</h3>
                  <p>{item.merged}</p>
                  <span>{item.reason}</span>
                </>
              )}
            />

            <ReviewListCard
              title="Материалы без evidence"
              meta={`${metrics.noEvidenceCount} материалов`}
              items={withoutEvidence}
              emptyText="Все выбранные сигналы содержат evidence"
              renderItem={(item) => (
                <>
                  <div className="digest-review-kicker">evidence check</div>
                  <h3>{safeTitle(item)}</h3>
                  <p>{item._qualitySource === "signal" ? "Выбранный сигнал требует ручной проверки evidence." : reasonLine(item)}</p>
                  {sourceLine(item) && <span>{sourceLine(item)}</span>}
                </>
              )}
            />
          </div>

          <div className="digest-right">
            <section className="digest-preview-card">
              <div className="section-heading">
                <p>Предпросмотр дайджеста</p>
                <span>preview</span>
              </div>
              <div className="digest-preview-window">
                <DigestPanel
                  digest={digest}
                  status={digestStatus}
                  className="digest-page-preview"
                  showDownload={false}
                />
                <div className="digest-preview-fade" aria-hidden="true" />
              </div>
              <button
                type="button"
                className="digest-open-full-button"
                onClick={() => setFullOpen(true)}
              >
                Открыть полный дайджест
              </button>
            </section>

            <ExportCenter
              result={result}
              signals={signals}
              digest={digest}
              currentUser={currentUser}
              selectedWatchlistTopics={selectedWatchlistTopics}
              onTrackEvent={onTrackEvent}
            />
          </div>
        </div>
      </main>

      <FullDigestModal
        open={fullOpen}
        onClose={() => setFullOpen(false)}
        result={result}
        signals={signals}
        digest={digest}
        status={digestStatus}
        currentUser={currentUser}
        selectedWatchlistTopics={selectedWatchlistTopics}
        onTrackEvent={onTrackEvent}
      />
    </div>
  );
}
