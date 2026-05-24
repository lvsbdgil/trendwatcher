const LABELS = [
  ["input_count", "Исходных публикаций"],
  ["after_cleaning", "После очистки"],
  ["not_fintech_count", "Отброшено как шум"],
  ["after_deduplication", "После дедупликации"],
  ["selected_signals", "Выбрано сигналов"],
];

function statValue(stats, key) {
  const value = Number(stats?.[key] ?? 0);
  return Number.isFinite(value) ? value : 0;
}

export default function StatsBar({ stats }) {
  return (
    <div className="stats-bar">
      {LABELS.map(([key, label]) => (
        <div className="stat-item" key={key}>
          <strong>{statValue(stats, key)}</strong>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}
