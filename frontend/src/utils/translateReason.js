// Human-readable Russian translation of backend reject/noise reasons.
// Backend may return technical English strings (from rule-based gate, LLM
// notes, or noise pattern hits). The UI should never show raw English to
// the user, but we keep the original mapping testable and fall back to a
// neutral Russian phrase for unknown patterns.

const FALLBACK = "Материал не прошёл фильтр релевантности";

const NOISE_KIND_RU = [
  [/conference|саммит|конференц/i, "конференция или мероприятие"],
  [/webinar|вебинар/i, "вебинар"],
  [/speaker|спикер/i, "анонс спикера"],
  [/summit/i, "саммит"],
  [/agenda|повестка/i, "повестка мероприятия"],
  [/award|premium|премия|награда/i, "премия или награда"],
  [/appoint|hir|chief marketing officer|кадров|назнач/i, "кадровое назначение"],
  [/vacancy|вакансия/i, "вакансия / найм"],
  [/podcast/i, "подкаст"],
  [/funding|invest|раунд|инвести/i, "финансирование без продуктового события"],
];

function translateNoiseKind(text) {
  const t = (text || "").trim();
  if (!t) return "общий шум";
  for (const [re, ru] of NOISE_KIND_RU) {
    if (re.test(t)) return ru;
  }
  return t;
}

function hasLatin(s) {
  return /[A-Za-z]/.test(s);
}

export function translateRejectReason(reason) {
  if (!reason) return FALLBACK;
  let text = String(reason).trim();
  if (!text) return FALLBACK;

  // Already Russian — nothing to translate.
  if (!hasLatin(text)) return text;

  // "both_llm_reject: <note>"
  let m = text.match(/^both[_ ]llm[_ ]reject\s*[:—-]?\s*(.*)$/i);
  if (m) {
    const inner = (m[1] || "").trim();
    if (!inner) return "Оба LLM отклонили этот материал";
    return `Оба LLM отклонили: ${translateRejectReason(inner)}`;
  }

  // "not fintech topic[: noise]: <reason>"
  m = text.match(/^not\s+fintech\s+topic\s*[:—-]?\s*(.*)$/i);
  if (m) {
    let inner = (m[1] || "").trim();
    inner = inner.replace(/^noise\s*[:—-]?\s*/i, "");
    if (!inner) return "Материал не относится к финтеху";
    return `Не финтех-тема: ${translateRejectReason(inner)}`;
  }

  // "noise item: generic without concrete product fact: <hit>"
  m = text.match(/^noise\s+item\s*[:—-]?\s*generic\s+without\s+concrete\s+product\s+fact\s*[:—-]?\s*(.*)$/i);
  if (m) {
    const hit = (m[1] || "").trim();
    return hit
      ? `Общий пересказ без конкретного факта — «${hit}»`
      : "Общий пересказ без конкретного продуктового факта";
  }

  // "noise item: <kind>"
  m = text.match(/^noise\s+item\s*[:—-]?\s*(.+)$/i);
  if (m) {
    const kind = translateNoiseKind(m[1]);
    return `Шум: ${kind}`;
  }

  // "finance term appears in non-actionable context: <hit>"
  m = text.match(/^finance\s+term\s+appears\s+in\s+non[- ]actionable\s+context\s*[:—-]?\s*(.*)$/i);
  if (m) {
    const hit = (m[1] || "").trim();
    return hit
      ? `Финансовый термин найден в нерелевантном контексте: «${hit}»`
      : "Финансовый термин найден в нерелевантном контексте";
  }

  // "funding-only item without product, regulation or customer scenario"
  if (/funding-only/i.test(text)) {
    return "Только финансирование без продукта, регулирования или клиентского сценария";
  }

  // "only N fintech anchor(s) without supporting context"
  if (/^only\s+\d+\s+fintech\s+anchor/i.test(text)) {
    return "Недостаточно финтех-якорей и нет подтверждающего контекста";
  }

  // "no fintech terms found in article body"
  if (/no\s+fintech\s+terms/i.test(text)) {
    return "Финтех-термины в тексте не найдены";
  }

  // "empty body"
  if (/empty\s+body/i.test(text)) {
    return "Пустой текст материала";
  }

  // "duplicate" / "dup"
  if (/\b(duplicate|dup)\b/i.test(text)) {
    return "Дубль: похожий материал уже учтён в другом сигнале";
  }

  // "not enough evidence" / "no concrete evidence"
  if (/not\s+enough\s+evidence|no\s+concrete\s+evidence/i.test(text)) {
    return "Недостаточно подтверждений для финтех-сигнала";
  }

  // "low relevance"
  if (/low\s+relevance/i.test(text)) {
    return "Низкая релевантность для банковских продуктов и финтех-сценариев";
  }

  // "no actionable signal"
  if (/no\s+actionable\s+signal/i.test(text)) {
    return "Нет прикладного сигнала для продуктовой или аналитической команды";
  }

  // "weak source"
  if (/weak\s+source|source\s+unavailable/i.test(text)) {
    return "Источник недостаточно надёжен или недоступен";
  }

  // "old news" / "stale"
  if (/old\s+news|stale/i.test(text)) {
    return "Новость устарела и не даёт актуального сигнала";
  }

  // "no concrete event"
  if (/no\s+concrete/i.test(text)) {
    return "Нет конкретного события для сигнала";
  }

  // Fallback
  return FALLBACK;
}
