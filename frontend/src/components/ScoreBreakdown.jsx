const FACTOR_LABELS = {
  bank_relevance: "Связь с банковскими продуктами",
  signal_type_weight: "Тип сигнала",
  novelty: "Новизна",
  source_quality: "Качество источника",
  recency: "Свежесть",
  evidence_strength: "Сила подтверждений",
  user_or_market_impact: "Влияние на пользователей / рынок",
  product_relevance: "Связь с банковскими продуктами",
  product_fit: "Связь с банковскими продуктами",
  bank_product_relevance: "Связь с банковскими продуктами",
  source_credibility: "Качество источника",
  credibility: "Качество источника",
  repeatability: "Повторяемость в источниках",
  cross_source: "Повторяемость в источниках",
  reach: "Повторяемость в источниках",
  market_impact: "Влияние на клиентский сценарий",
  client_impact: "Влияние на клиентский сценарий",
  actionability: "Влияние на клиентский сценарий",
  impact: "Влияние на клиентский сценарий",
  noise_penalty: "Штраф за шум",
  penalties: "Штрафы",
  noise_level: "Уровень шума",
  primacy: "Качество источника",
};

const MAX_BY_FACTOR = {
  bank_relevance: 25,
  signal_type_weight: 20,
  novelty: 15,
  source_quality: 15,
  recency: 10,
  evidence_strength: 10,
  user_or_market_impact: 5,
  product_fit: 30,
  product_relevance: 30,
  actionability: 20,
  source_credibility: 15,
  cross_source: 5,
  penalties: 30,
  noise_penalty: 30,
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalizeEntry(key, value) {
  if (typeof value === "number") {
    const max = MAX_BY_FACTOR[key] || 100;
    const width = key === "noise_penalty" || key === "penalties"
      ? clamp(Math.abs(value), 0, max) / max * 100
      : clamp(value, 0, max) / max * 100;
    return { score: value, why: "", width };
  }

  if (value && typeof value === "object") {
    const rawScore = Number(value.score ?? value.value ?? 0);
    const score = Number.isFinite(rawScore) ? rawScore : 0;
    const max = Number(value.max ?? MAX_BY_FACTOR[key] ?? 30);
    return {
      score,
      why: value.why || value.reason || "",
      width: clamp(Math.abs(score), 0, max) / max * 100,
    };
  }

  return null;
}

function formatScore(score) {
  if (!Number.isFinite(score)) return "нет данных";
  return Number.isInteger(score) ? score : score.toFixed(1);
}

export default function ScoreBreakdown({ score = {} }) {
  const entries = Object.entries(score)
    .map(([key, value]) => [key, normalizeEntry(key, value)])
    .filter(([, value]) => value);

  if (!entries.length) {
    return <div className="no-data">Нет данных по этому блоку</div>;
  }

  return (
    <ul className="factors-list">
      {entries.map(([key, value]) => (
        <li key={key} className={key === "penalties" || key === "noise_penalty" || value.score < 0 ? "is-penalty" : ""}>
          <span>{FACTOR_LABELS[key] || key}</span>
          <div className="factor-bar">
            <span style={{ width: `${value.width}%` }}></span>
          </div>
          <span className="factor-val">{formatScore(value.score)}</span>
          {value.why && <small className="factor-why">{value.why}</small>}
        </li>
      ))}
    </ul>
  );
}
