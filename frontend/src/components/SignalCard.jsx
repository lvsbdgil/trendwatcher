import ScoreBreakdown from "./ScoreBreakdown";

const { useState } = React;

const KIND_LABELS = {
  primary: "первоисточник",
  original: "первоисточник",
  trusted_media: "источник",
  media: "источник",
  reprint: "пересказ",
  retelling: "пересказ",
  rewrite: "пересказ",
  needs_check: "нужна проверка",
  unknown: "источник",
};

function kindLabel(kind) {
  return KIND_LABELS[kind] || "источник";
}

function kindBadgeClass(kind) {
  if (kind === "primary" || kind === "original") return "src-kind-primary";
  if (kind === "reprint" || kind === "retelling" || kind === "rewrite") return "src-kind-reprint";
  if (kind === "needs_check") return "src-kind-check";
  return "src-kind-unknown";
}

function hotnessLevel(v) {
  if (v > 90) return { label: "критичная", cls: "hl-critical" };
  if (v > 75) return { label: "высокая", cls: "hl-high" };
  if (v > 55) return { label: "средняя", cls: "hl-mid" };
  if (v > 30) return { label: "низкая", cls: "hl-low" };
  return { label: "шум", cls: "hl-noise" };
}

function clampHotness(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

function cleanText(value, fallback = "Нет данных по этому блоку") {
  if (value == null) return fallback;
  const text = String(value)
    .replace(/[*`#]/g, "")
    .replace(/^\s*[-•]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text || text === "undefined" || text === "null") return fallback;
  return text;
}

function displayUrl(url) {
  if (!url) return "";
  if (url.startsWith("manual://")) return "ручной ввод";
  try {
    const parsed = new URL(url);
    return `${parsed.hostname}${parsed.pathname === "/" ? "" : parsed.pathname}`.replace(/\/$/, "");
  } catch {
    return url.replace(/^https?:\/\//, "").replace(/\/$/, "");
  }
}

function sourceUrl(src) {
  return typeof src === "string" ? src : src?.url;
}

function sourceKind(src) {
  if (typeof src !== "object" || !src) return "unknown";
  if (src.needs_check || src.needsCheck) return "needs_check";
  return src.kind || src.type || "unknown";
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  async function handleClick(e) {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch {}
      ta.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  return (
    <button className="copy-btn" onClick={handleClick} aria-label="Копировать черновик">
      <span className="copy-btn-ico" aria-hidden="true">{copied ? "✓" : "⧉"}</span>
      <span>{copied ? "Скопировано" : "Копировать"}</span>
    </button>
  );
}

const CONSENSUS_LABELS = {
  both_agree:    { label: "Оба LLM согласны",   cls: "cs-agree" },
  both_reject:   { label: "Оба отклонили",       cls: "cs-reject" },
  openai_holds:  { label: "OpenAI настоял",      cls: "cs-holds" },
  gemini_flags:  { label: "Gemini флагнул",      cls: "cs-flags" },
  single_llm:    { label: "Один LLM",            cls: "cs-single" },
  no_llm:        null,
};

function ConsensusBadge({ signal }) {
  const status = signal.consensus_status;
  if (!status || status === "no_llm") return null;

  const meta = CONSENSUS_LABELS[status];
  if (!meta) return null;

  const geminiNote = signal.gemini_note;
  const openaiNote = signal.openai_review_note;

  return (
    <div className={`consensus-badge ${meta.cls}`}>
      <span className="cs-label">◆ {meta.label}</span>
      {geminiNote && (
        <span className="cs-note cs-gemini">Gemini: {geminiNote}</span>
      )}
      {openaiNote && (
        <span className="cs-note cs-openai">OpenAI: {openaiNote}</span>
      )}
    </div>
  );
}

export default function SignalCard({ signal, index, defaultOpen = false, static: isStatic = false }) {
  const [open, setOpen] = useState(defaultOpen);

  const hotness = clampHotness(signal.hotness);
  const hl = hotnessLevel(hotness);
  const sources = Array.isArray(signal.sources) ? signal.sources : [];
  const evidence = Array.isArray(signal.evidence) ? signal.evidence : [];
  const duplicateCount = signal.duplicate_group?.source_count || signal.duplicate_count || sources.length;
  const factors = signal.score_explanation || signal.hotness_factors || {};

  const confidenceNumber = Number(signal.confidence);
  const hasConfidence = Number.isFinite(confidenceNumber);
  const confidenceDecimal = hasConfidence
    ? (confidenceNumber <= 1 ? confidenceNumber.toFixed(2) : (confidenceNumber / 100).toFixed(2))
    : null;
  const confidencePercent = hasConfidence
    ? `${Math.round(confidenceNumber <= 1 ? confidenceNumber * 100 : confidenceNumber)}%`
    : null;
  const confidenceLevel = hasConfidence
    ? (confidenceNumber > 0.7 ? { label: "высокая", cls: "conf-level-high" }
      : confidenceNumber >= 0.45 ? { label: "средняя", cls: "conf-level-mid" }
      : { label: "низкая", cls: "conf-level-low" })
    : null;

  const title = cleanText(signal.headline || signal.title, "Без заголовка");
  const category = cleanText(signal.category, "Без категории");
  const whyNow = cleanText(signal.whyNow || signal.why_now);
  const summary = cleanText(signal.summary);
  const draft = cleanText(signal.draft, "");
  const dateText = signal.date ? cleanText(signal.date, "") : "";
  const indexLabel = Number.isFinite(Number(index))
    ? String(Number(index) + 1).padStart(2, "0")
    : null;

  return (
    <article className={`signal-card ${open ? "is-open" : ""} ${isStatic ? "is-static" : ""}`}>
      <button
        type="button"
        className="sig-head"
        onClick={() => { if (!isStatic) setOpen((v) => !v); }}
        aria-expanded={open}
        aria-disabled={isStatic ? "true" : undefined}
      >
        <div className="sig-score">
          {indexLabel && <span className="sig-score-index">#{indexLabel}</span>}
          <span className="sig-score-num">{hotness}</span>
          <span className="sig-score-bar" style={{ "--w": `${hotness}%` }} aria-hidden="true"></span>
          <span className={`hotness-level ${hl.cls}`}>{hl.label}</span>
          <span className="sig-score-cat">{category}</span>
        </div>

        <div className="sig-body">
          <h3 className="sig-title">{title}</h3>
          {whyNow && <p className="sig-why">{whyNow}</p>}
          <div className="sig-meta">
            {dateText && <span className="sig-meta-item">{dateText}</span>}
            {sources.length > 0 && (
              <span className="sig-meta-item">{sources.length} ист.</span>
            )}
            {duplicateCount > 1 && (
              <span className="sig-meta-item">склеено {duplicateCount}</span>
            )}
            {confidencePercent != null && (
              <span className="sig-meta-item sig-meta-conf">
                уверенность {confidencePercent}
              </span>
            )}
            <span className="sig-meta-spacer" />
            {!isStatic && (
              <span className="sig-chev" aria-hidden="true">{open ? "− свернуть" : "+ подробнее"}</span>
            )}
          </div>
        </div>
      </button>

      {open && (
        <div className="sig-detail">
          <div className="detail-label">Краткая выжимка</div>
          <p className="detail-summary">{summary}</p>

          {evidence.length > 0 && (
            <>
              <div className="detail-label" style={{ marginTop: 18 }}>Подтверждения</div>
              <ul className="evidence-list">
                {evidence.map((item, i) => (
                  <li key={i}>
                    <q>{cleanText(typeof item === "string" ? item : item.quote, "Нет данных")}</q>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="sig-detail-grid">
            <div className="sig-detail-col">
              <div className="detail-label">Черновик для команды</div>
              <div className="draft-block">
                <p>{draft || "Нет данных по этому блоку"}</p>
                {draft && <CopyButton text={draft} />}
              </div>
            </div>

            <div className="sig-detail-col">
              <div className="detail-label">Источники · {sources.length}</div>
              {duplicateCount > 1 && (
                <div className="duplicate-note">
                  Найдены дубли и пересказы: {duplicateCount} материалов по одному событию.
                </div>
              )}
              {sources.length > 0 ? (
                <ul className="src-list">
                  {sources.map((src, i) => {
                    const url = sourceUrl(src);
                    const kind = sourceKind(src);
                    const isPrimary = kind === "primary" || kind === "original";
                    const label = displayUrl(url) || cleanText(src?.name, "источник");
                    const isClickable = url && /^https?:\/\//.test(url);
                    return (
                      <li key={`${url || label}-${i}`} className={`src-item ${isPrimary ? "is-primary" : ""}`}>
                        <span className={`src-dot ${isPrimary ? "primary" : ""}`}></span>
                        {isClickable ? (
                          <a href={url} target="_blank" rel="noreferrer" title={url}>{label}</a>
                        ) : (
                          <span className="src-text">{label}</span>
                        )}
                        <span className={`src-kind ${isPrimary ? "primary" : ""} ${kindBadgeClass(kind)}`}>
                          {kindLabel(kind)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div className="no-data">Нет данных по этому блоку</div>
              )}
            </div>

            <div className="sig-detail-col">
              <div className="detail-label">Почему такая оценка</div>
              <ScoreBreakdown score={factors} />
              <div className="detail-foot">
                {hasConfidence ? (
                  <span className={`detail-foot-conf ${confidenceLevel.cls}`}>
                    Уверенность <b>{confidenceDecimal}</b>
                    <span className="detail-foot-conf-pct">· {confidencePercent}</span>
                    <span className={`conf-level ${confidenceLevel.cls}`}>{confidenceLevel.label}</span>
                  </span>
                ) : (
                  <span>Уверенность <b>нет данных</b></span>
                )}
                {signal.importance_reason && (
                  <p className="detail-foot-reason">
                    <b>Итог:</b> {cleanText(signal.importance_reason, "")}
                  </p>
                )}
                <ConsensusBadge signal={signal} />
              </div>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
