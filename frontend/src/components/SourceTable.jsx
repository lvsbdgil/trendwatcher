import { translateRejectReason } from "../utils/translateReason";

const { useState } = React;

const IMPORTANCE_LABEL = {
  bank_relevance: "связь с банком",
  signal_type_weight: "тип сигнала",
  novelty: "новизна",
  source_quality: "качество источника",
  recency: "свежесть",
  evidence_strength: "сила доказательств",
  user_or_market_impact: "влияние на сценарий",
};

const IMPORTANCE_MAX = {
  bank_relevance: 25,
  signal_type_weight: 20,
  novelty: 15,
  source_quality: 15,
  recency: 10,
  evidence_strength: 10,
  user_or_market_impact: 5,
};

const CONFIDENCE_LABEL = {
  has_valid_title: "нормальный заголовок",
  has_publication_date: "есть дата",
  extraction_quality: "качество извлечения",
  source_reliability: "надёжность источника",
  has_primary_source: "первоисточник",
  cross_source_confirmation: "подтверждение",
  entity_extraction_quality: "сущности",
  llm_json_validity: "валидность LLM",
  duplicate_or_repost_penalty: "штраф за перепечатку",
  weak_content_penalty: "штраф за слабый текст",
  fintech_anchor_density: "плотность финтех-терминов",
  relevance_certainty: "уверенность классификатора",
  concrete_event_signal: "конкретное событие",
};

function importanceValue(article) {
  const raw = article.importance ?? article.hotness ?? 0;
  const value = Number(raw);
  if (Number.isFinite(value)) return Math.max(0, Math.min(100, Math.round(value)));
  return 0;
}

function confidenceValue(article) {
  const value = Number(article.confidence ?? 0);
  if (!Number.isFinite(value)) return 0;
  return value <= 1 ? value : value / 100;
}

function formatConfidence(value) {
  return value.toFixed(2);
}

function confidencePercent(value) {
  return `${Math.round(value * 100)}%`;
}

function confidenceLevel(value) {
  if (value < 0.45) return { label: "низкая", cls: "conf-level-low" };
  if (value <= 0.7) return { label: "средняя", cls: "conf-level-mid" };
  return { label: "высокая", cls: "conf-level-high" };
}

function importanceLevel(value) {
  if (value <= 30) return { label: "шум", cls: "level-noise" };
  if (value <= 55) return { label: "низкая", cls: "level-low" };
  if (value <= 75) return { label: "средняя", cls: "level-mid" };
  if (value <= 90) return { label: "высокая", cls: "level-high" };
  return { label: "критичная", cls: "level-critical" };
}

function evidenceText(article) {
  const evidence = article.evidence || [];
  if (!evidence.length) return "";
  const first = evidence[0];
  return typeof first === "string" ? first : first.quote;
}

function whyNowText(article) {
  return article.why_now || article.whyNow || article.bank_relevance || article.summary_fact || "";
}

function safeText(value, fallback = "—") {
  if (value == null) return fallback;
  const text = String(value).trim();
  if (!text || text === "undefined" || text === "null") return fallback;
  return text;
}

function sourceText(article) {
  if (article.source) return article.source;
  const sources = article.sources || [];
  const first = sources[0];
  if (typeof first === "string") return first;
  return first?.name || first?.url || "";
}

function ImportanceBreakdown({ breakdown }) {
  if (!breakdown || typeof breakdown !== "object") return null;
  const rows = Object.entries(breakdown).filter(([k]) => !k.startsWith("_"));
  if (!rows.length) return null;
  return (
    <div className="score-breakdown">
      <div className="score-breakdown-title">Из чего складывается важность</div>
      <ul>
        {rows.map(([key, value]) => {
          const max = IMPORTANCE_MAX[key];
          return (
            <li key={key}>
              <span className="bd-label">{IMPORTANCE_LABEL[key] || key}</span>
              <span className="bd-bar">
                <span
                  className="bd-bar-fill"
                  style={{ width: `${max ? Math.min(100, (value / max) * 100) : 0}%` }}
                />
              </span>
              <span className="bd-value">
                {value}{max ? `/${max}` : ""}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ConfidenceBreakdown({ breakdown }) {
  if (!breakdown || typeof breakdown !== "object") return null;
  const entries = Object.entries(breakdown);
  if (!entries.length) return null;
  return (
    <div className="score-breakdown">
      <div className="score-breakdown-title">Что повлияло на уверенность</div>
      <ul className="score-breakdown-flat">
        {entries.map(([key, value]) => {
          const label = CONFIDENCE_LABEL[key] || key;
          let display;
          if (typeof value === "boolean") display = value ? "да" : "нет";
          else display = String(value);
          return (
            <li key={key}>
              <span className="bd-label">{label}</span>
              <span className="bd-value">{display}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function DetailsContent({ article, isNoiseTable }) {
  const confidence = confidenceValue(article);
  const confidenceLine = `${formatConfidence(confidence)} · ${confidencePercent(confidence)}`;
  return (
    <div className="details-content">
      {isNoiseTable && (
        <p>{translateRejectReason(article.rejection_reason || article.reject_reason)}</p>
      )}
      {!isNoiseTable && (
        <>
          {safeText(article.importance_reason, "") && (
            <p><b>Почему важно:</b> {safeText(article.importance_reason, "")}</p>
          )}
          {safeText(whyNowText(article), "") && (
            <p><b>Почему сейчас:</b> {safeText(whyNowText(article), "")}</p>
          )}
          <p>
            <b>Уверенность:</b> {confidenceLine}
            {safeText(article.confidence_reason, "") && (
              <> — {safeText(article.confidence_reason, "")}</>
            )}
          </p>
          {safeText(evidenceText(article), "") && (
            <p><b>Подтверждение:</b> {safeText(evidenceText(article), "")}</p>
          )}
          <ImportanceBreakdown breakdown={article.importance_breakdown} />
          <ConfidenceBreakdown breakdown={article.confidence_breakdown} />
          {article.primary_source_url && (
            <p className="primary-source-line">
              <b>Первоисточник:</b>{" "}
              <a href={article.primary_source_url} target="_blank" rel="noreferrer">
                {article.primary_source_url}
              </a>
            </p>
          )}
        </>
      )}
    </div>
  );
}

function ArticleRow({
  article,
  index,
  isNoiseTable,
  openKey,
  setOpenKey,
  selectMode,
  isSelected,
  onSelect,
}) {
  const importance = importanceValue(article);
  const level = importanceLevel(importance);
  const confidence = confidenceValue(article);
  const cLevel = confidenceLevel(confidence);
  const duplicateCount = Number(article.duplicate_count || 0);
  const sourceLabel = safeText(sourceText(article));

  const rowKey = `${article.url || article.title || article.headline || "row"}-${index}`;
  const isOpen = !selectMode && openKey === rowKey;

  function toggleInlineExpand() {
    setOpenKey(isOpen ? null : rowKey);
  }

  function handleDetailsClick() {
    if (selectMode) {
      onSelect?.(index);
    } else {
      toggleInlineExpand();
    }
  }

  const rowClasses = [
    isOpen ? "is-open" : "",
    selectMode && isSelected ? "is-selected" : "",
  ].filter(Boolean).join(" ");

  const matchedTopics = Array.isArray(article._matchedTopics) ? article._matchedTopics : [];

  return (
    <>
      <tr className={rowClasses}>
        <td className="title-cell" data-label="Заголовок">
          <div className="title-cell-line">
            <span>{safeText(article.title || article.headline)}</span>
            {duplicateCount > 0 && (
              <span className="dup-badge" title="Перепечатки объединены">
                +{duplicateCount} дубл.
              </span>
            )}
            {matchedTopics.length > 0 && (
              <span
                className="topic-badge"
                title={`По вашим темам: ${matchedTopics.join(", ")}`}
              >
                по вашей теме
              </span>
            )}
          </div>
        </td>
        <td className="src-cell" data-label="Источник" title={sourceLabel}>
          <span className="src-cell-text">{sourceLabel}</span>
        </td>
        <td className="cat-cell" data-label="Категория">{safeText(article.category)}</td>
        <td className="hot-cell" data-label="Важность">
          <div className="hot-cell-inner">
            <span className={`hot-number ${level.cls}`}>{importance}</span>
            <span className={`hot-level ${level.cls}`}>{level.label}</span>
          </div>
        </td>
        <td className="conf-cell" data-label="Уверенность">
          <div className="conf-cell-inner">
            <span className="conf-percent-main" title={`Точное значение: ${formatConfidence(confidence)}`}>
              {confidencePercent(confidence)}
            </span>
            <span className={`conf-level ${cLevel.cls}`}>{cLevel.label}</span>
          </div>
        </td>
        <td className="detail-cell" data-label={isNoiseTable ? "Причина" : "Детали"}>
          <button
            type="button"
            className={`detail-toggle ${isOpen ? "is-open" : ""} ${selectMode && isSelected ? "is-selected" : ""}`}
            onClick={handleDetailsClick}
            aria-expanded={selectMode ? undefined : isOpen}
            aria-pressed={selectMode ? isSelected : undefined}
          >
            {selectMode ? (
              <>
                <span className="detail-toggle-marker" aria-hidden="true">{isSelected ? "●" : "▸"}</span>
                <span>{isSelected ? "выбран" : "подробнее"}</span>
              </>
            ) : (
              <>
                <span className="detail-toggle-marker" aria-hidden="true">{isOpen ? "−" : "+"}</span>
                <span>{isNoiseTable ? "причина" : "почему важно"}</span>
              </>
            )}
          </button>
        </td>
      </tr>
      {isOpen && (
        <tr className="detail-row">
          <td colSpan={6} className="detail-row-cell">
            <DetailsContent article={article} isNoiseTable={isNoiseTable} />
          </td>
        </tr>
      )}
    </>
  );
}

export default function SourceTable({
  articles,
  title = "Материалы",
  emptyText = "Добавьте ссылку, текст публикации или запустите демо-пример.",
  isNoiseTable = false,
  countText,
  selectedIndex = null,
  onSelect = null,
}) {
  const [openKey, setOpenKey] = useState(null);
  const selectMode = typeof onSelect === "function";

  return (
    <section className={`table-section ${isNoiseTable ? "noise-table-section" : ""}`} id={isNoiseTable ? "rejected-noise" : "sources"}>
      <div className="section-heading">
        <p>{title}</p>
        <span>{countText || `${articles.length} материалов`}</span>
      </div>

      <div className="table-wrap signals-table-wrapper">
        <table className="signals-table">
          <colgroup>
            <col className="headline-col" />
            <col className="source-col" />
            <col className="category-col" />
            <col className="hotness-col" />
            <col className="confidence-col" />
            <col className="details-col" />
          </colgroup>
          <thead>
            <tr>
              <th>Заголовок</th>
              <th>Источник</th>
              <th>Категория</th>
              <th title="Важность сигнала, 0–100">Важность</th>
              <th title="Уверенность в карточке, 0–1">Уверенность</th>
              <th>{isNoiseTable ? "Причина" : "Детали"}</th>
            </tr>
          </thead>
          <tbody>
            {articles.length === 0 && (
              <tr>
                <td colSpan="6" className="empty-cell">
                  {emptyText}
                </td>
              </tr>
            )}
            {articles.map((article, index) => (
              <ArticleRow
                key={`${article.url || article.title || article.headline}-${index}`}
                article={article}
                index={index}
                isNoiseTable={isNoiseTable}
                openKey={openKey}
                setOpenKey={setOpenKey}
                selectMode={selectMode}
                isSelected={selectMode && selectedIndex === index}
                onSelect={onSelect}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
