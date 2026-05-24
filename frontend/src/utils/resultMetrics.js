function statNumber(...values) {
  for (const value of values) {
    const num = Number(value);
    if (Number.isFinite(num) && num >= 0) return Math.round(num);
  }
  return null;
}

export function hasEvidence(signal) {
  const evidence = signal?.evidence;
  if (Array.isArray(evidence)) {
    return evidence.some((item) => {
      const quote = typeof item === "string" ? item : item?.quote;
      return String(quote || "").trim().length >= 20;
    });
  }
  return String(evidence || "").trim().length >= 20;
}

export function duplicateCount(result, signals = []) {
  const fromStats = statNumber(
    result?.stats?.duplicates_count,
    result?.stats?.duplicate_count,
    result?.duplicates_count,
  );
  if (fromStats != null) return fromStats;

  if (Array.isArray(result?.duplicates)) return result.duplicates.length;

  return signals.reduce((sum, signal) => {
    const groupCount = Number(signal?.duplicate_group?.source_count ?? signal?.duplicate_count ?? 0);
    return sum + Math.max(0, groupCount - 1);
  }, 0);
}

export function noiseCount(result, rejectedRows = []) {
  const fromStats = statNumber(
    result?.stats?.total_rejected_count,
    result?.stats?.rejected_count,
    result?.stats?.noise_count,
    result?.stats?.not_fintech_count,
    result?.rejected_count,
  );
  return fromStats ?? rejectedRows.length;
}

export function noEvidenceRows(result, signals = [], rejectedRows = []) {
  const rows = [];
  const seen = new Set();
  const add = (item, source) => {
    if (!item) return;
    const key = `${source}|${item.url || ""}|${item.title || item.headline || ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    rows.push({ ...item, _qualitySource: source });
  };

  signals.forEach((signal) => {
    if (!hasEvidence(signal)) add(signal, "signal");
  });

  rejectedRows.forEach((item) => {
    const reason = String(item?.rejection_reason || item?.reject_reason || item?.reason || "").toLowerCase();
    if (reason.includes("evidence")) add(item, "rejected");
  });

  return rows;
}

export function noEvidenceCount(result, signals = [], rejectedRows = []) {
  const fromStats = statNumber(result?.stats?.noise_breakdown?.no_evidence);
  return Math.max(fromStats ?? 0, noEvidenceRows(result, signals, rejectedRows).length);
}

export function duplicateRows(result, signals = []) {
  const rows = [];

  if (Array.isArray(result?.duplicates)) {
    result.duplicates.forEach((item, index) => {
      rows.push({
        id: `log-${index}`,
        kept: item?.kept || item?.title || "Основной материал",
        merged: item?.merged || item?.removed?.join(", ") || "Дубль / перепечатка",
        reason: item?.reason || "Похожее событие или заголовок",
      });
    });
  }

  signals.forEach((signal, index) => {
    const count = Number(signal?.duplicate_count || 0);
    const sourceCount = Number(signal?.duplicate_group?.source_count || 0);
    const duplicateTotal = Math.max(count, sourceCount > 0 ? sourceCount - 1 : 0);
    if (duplicateTotal <= 0) return;
    rows.push({
      id: `signal-${index}`,
      kept: signal?.headline || signal?.title || "Сигнал",
      merged: `${duplicateTotal} дубл./перепечаток`,
      reason: "Объединено в одну карточку сигнала",
    });
  });

  return rows;
}

export function digestMetrics(result, signals = [], rejectedRows = [], selectedWatchlistTopics = []) {
  return {
    signalCount: signals.length,
    watchlistCount: Array.isArray(selectedWatchlistTopics) ? selectedWatchlistTopics.length : 0,
    duplicatesCount: duplicateCount(result, signals),
    noiseCount: noiseCount(result, rejectedRows),
    noEvidenceCount: noEvidenceCount(result, signals, rejectedRows),
  };
}
