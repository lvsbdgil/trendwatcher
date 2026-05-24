function countSources(signal) {
  return Array.isArray(signal.sources) ? signal.sources.length : 0;
}

function duplicateCount(result, signals) {
  const fromStats = Number(result?.stats?.duplicates_count ?? result?.stats?.duplicate_count ?? result?.duplicates_count);
  if (Number.isFinite(fromStats) && fromStats > 0) return Math.round(fromStats);

  return signals.reduce((sum, signal) => {
    const groupCount = Number(signal.duplicate_group?.source_count ?? signal.duplicate_count ?? 0);
    return sum + Math.max(0, groupCount - 1);
  }, 0);
}

function averageConfidence(signals) {
  const values = signals
    .map((signal) => Number(signal.confidence ?? signal.hotness))
    .filter(Number.isFinite);

  if (!values.length) return "нет данных";

  const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
  const normalized = avg <= 1 ? avg * 100 : avg;
  return `${Math.round(normalized)}%`;
}

function sourceShare(signals) {
  if (!signals.length) return "нет данных";
  const withSources = signals.filter((signal) => countSources(signal) > 0).length;
  return `${Math.round((withSources / signals.length) * 100)}%`;
}

function rejectedCount(result, rejectedRows) {
  const fromStats = Number(
    result?.stats?.rejected_count ??
    result?.stats?.noise_count ??
    result?.stats?.not_fintech_count ??
    result?.rejected_count
  );
  if (Number.isFinite(fromStats) && fromStats >= 0) return Math.round(fromStats);
  return rejectedRows.length;
}

function Skeleton() {
  return <span className="quality-skeleton" aria-label="загружается">▮▮▮</span>;
}

function ConsensusCard({ active, loading, agree, reject }) {
  if (loading) {
    return (
      <div className="quality-card quality-card-consensus is-loading">
        <strong><Skeleton /></strong>
        <span>Согласие LLM</span>
      </div>
    );
  }
  if (!active) {
    return (
      <div className="quality-card quality-card-consensus quality-gemini-off">
        <strong>—</strong>
        <span>Gemini не подключён</span>
      </div>
    );
  }
  return (
    <div className="quality-card quality-card-consensus">
      <div className="quality-consensus-row">
        <div className="quality-consensus-cell">
          <strong className="quality-consensus-num quality-consensus-agree">{agree}</strong>
          <span className="quality-consensus-sublabel">согласны</span>
        </div>
        <div className="quality-consensus-cell">
          <strong className="quality-consensus-num quality-consensus-reject">{reject}</strong>
          <span className="quality-consensus-sublabel">отклонили</span>
        </div>
      </div>
      <span>Консенсус двух LLM по сигналам</span>
    </div>
  );
}

export default function QualityPanel({ result, signals = [], rejectedRows = [], loading = false }) {
  const geminiActive = Boolean(result?.stats?.gemini_active);
  const bothAgree = Number(result?.stats?.consensus_both_agree ?? 0);
  const bothReject = Number(result?.stats?.consensus_both_reject ?? 0);

  const metrics = [
    ["Материалы, отброшенные как шум", loading ? null : rejectedCount(result, rejectedRows)],
    ["Найденные дубли и пересказы", loading ? null : duplicateCount(result, signals)],
    ["Доля сигналов с проверяемыми источниками", loading ? null : sourceShare(signals)],
    ["Средняя уверенность по сигналам", loading ? null : averageConfidence(signals)],
  ];

  return (
    <section className="quality-panel">
      <div className="section-heading">
        <p>Контроль качества</p>
        <span>{loading ? "в процессе" : "проверка результата"}</span>
      </div>
      <div className="quality-grid">
        {metrics.map(([label, value]) => (
          <div className={`quality-card${loading ? " is-loading" : ""}`} key={label}>
            <strong>{loading ? <Skeleton /> : value}</strong>
            <span>{label}</span>
          </div>
        ))}
        <div className="quality-card quality-check">
          <strong>top-3</strong>
          <span>Ручная проверка top-3 сигналов перед отправкой в команду</span>
        </div>
        <ConsensusCard
          active={geminiActive}
          loading={loading}
          agree={bothAgree}
          reject={bothReject}
        />
      </div>
    </section>
  );
}
