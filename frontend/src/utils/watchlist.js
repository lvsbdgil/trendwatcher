/**
 * Watchlist — словарь финтех-тем и матчинг сигналов.
 *
 * Один сигнал может попасть в несколько тем. Матчинг идёт по нескольким
 * текстовым полям сигнала (headline/summary/why_now/draft/category/tags/...).
 * Совпадение по любому ключевому слову даёт попадание темы.
 */

export const WATCHLIST_TOPICS = [
  {
    id: "payments",
    label: "Платежи",
    keywords: [
      "платеж", "платёж", "оплата", "payment", " pay ", "перевод", "transfer",
      "эквайринг", "acquiring", " qr ", "qr-", " p2p", "merchant", "checkout",
      "платёжный", "платежный",
    ],
  },
  {
    id: "bnpl",
    label: "BNPL",
    keywords: [
      "bnpl", "buy now pay later", "рассрочка", "рассрочку", "pay later",
      "installment", "installments", "оплата частями",
    ],
  },
  {
    id: "cards",
    label: "Карты",
    keywords: [
      "карта", "карты", "карт ", "card ", "cards", " debit", " credit",
      "виртуальная карта", "virtual card", "card issuing", "issuer",
      "дебет", "кредитка",
    ],
  },
  {
    id: "mobile_banking",
    label: "Мобильный банк",
    keywords: [
      "мобильный банк", "мобильное приложение", "mobile banking", "banking app",
      "мобильного банка", "в приложении", "in-app", " app ", "приложение банка",
    ],
  },
  {
    id: "ux",
    label: "UX-механики",
    keywords: [
      " ux", "u/x", "онбординг", "onboarding", "user experience",
      "интерфейс", "interface", "сценарий", "user flow", "user journey",
      "персонализация", "personalization", "редизайн", "redesign",
    ],
  },
  {
    id: "ai_banking",
    label: "AI в банкинге",
    keywords: [
      " ai ", "ai-", "ии ", " ии,", "искусственный интеллект", "llm",
      "genai", "gen-ai", "чат-бот", "chatbot", "ai assistant", "ассистент",
      "скоринг", "scoring", "machine learning", "machine-learning", "ml-модел",
    ],
  },
  {
    id: "regulation",
    label: "Регулирование",
    keywords: [
      "регулирование", "регулятор", "цб ", "цб,", "central bank", "compliance",
      "комплаенс", " law", " закон", "законопроект", "aml", "kyc",
      "регулирующ", "license", "лицензи",
    ],
  },
  {
    id: "loyalty",
    label: "Loyalty",
    keywords: [
      "loyalty", "лояльность", "кэшбэк", "кэшбек", "кешбэк", "cashback",
      "rewards", "reward", "бонус", "бонусы", "подписк", "subscription",
      "программа лояльности",
    ],
  },
  {
    id: "smb",
    label: "SMB banking",
    keywords: [
      "smb", "малый бизнес", "малого бизнеса", "мсб", "предприниматель",
      "ип ", "merchant", "b2b", "business banking", "self-employed",
      "самозанят",
    ],
  },
  {
    id: "open_banking",
    label: "Open banking",
    keywords: [
      "open banking", "open finance", " api ", "api-", "psd2", "psd3",
      "account aggregation", "открытый банкинг", "открытые api",
      "data sharing",
    ],
  },
];

export const DEFAULT_WATCHLIST = ["payments", "cards", "ux", "ai_banking"];

export const TOPIC_BY_ID = WATCHLIST_TOPICS.reduce((acc, t) => {
  acc[t.id] = t;
  return acc;
}, {});

function pickText(...values) {
  return values
    .filter((v) => v != null)
    .map((v) => {
      if (Array.isArray(v)) return v.join(" ");
      if (typeof v === "object") {
        try { return JSON.stringify(v); } catch { return ""; }
      }
      return String(v);
    })
    .join(" ")
    .toLowerCase();
}

function signalToHaystack(signal) {
  if (!signal || typeof signal !== "object") return "";
  const sources = Array.isArray(signal.sources)
    ? signal.sources.map((s) => `${s?.url || ""} ${s?.kind || ""}`).join(" ")
    : "";
  return pickText(
    signal.headline,
    signal.title,
    signal.summary,
    signal.why_now,
    signal.whyNow,
    signal.draft,
    signal.category,
    signal.tags,
    signal.importance_reason,
    signal.importanceReason,
    signal.score_explanation,
    signal.evidence,
    sources,
  );
}

function matchTopics(haystack, selectedIds) {
  const matched = [];
  for (const id of selectedIds) {
    const topic = TOPIC_BY_ID[id];
    if (!topic) continue;
    const hit = topic.keywords.some((kw) => haystack.includes(kw.toLowerCase()));
    if (hit) matched.push(id);
  }
  return matched;
}

/**
 * Отфильтровать сигналы по выбранным темам.
 * Возвращает:
 *  - signals: сигналы, попавшие хотя бы в одну тему, с полем `matchedTopics`;
 *  - countsByTopic: { topicId: number };
 *  - matchedCount, selectedCount.
 */
export function filterSignalsByWatchlist(signals, selectedIds) {
  const ids = Array.isArray(selectedIds) ? selectedIds.filter(Boolean) : [];
  const countsByTopic = ids.reduce((acc, id) => { acc[id] = 0; return acc; }, {});

  if (!Array.isArray(signals) || signals.length === 0 || ids.length === 0) {
    return { signals: [], countsByTopic, matchedCount: 0, selectedCount: ids.length };
  }

  const out = [];
  for (const signal of signals) {
    const haystack = signalToHaystack(signal);
    if (!haystack) continue;
    const matched = matchTopics(haystack, ids);
    if (matched.length === 0) continue;
    matched.forEach((id) => { countsByTopic[id] = (countsByTopic[id] || 0) + 1; });
    out.push({ ...signal, matchedTopics: matched });
  }

  return {
    signals: out,
    countsByTopic,
    matchedCount: out.length,
    selectedCount: ids.length,
  };
}

export function topicLabel(id) {
  return TOPIC_BY_ID[id]?.label || id;
}

/**
 * Получить список ID тем, под которые подходит данный сигнал.
 * В отличие от filterSignalsByWatchlist, не отбрасывает сигналы — нужен,
 * чтобы навешать бейдж «по вашей теме» поверх общей ленты.
 */
export function getMatchedTopics(signal, selectedIds) {
  const ids = Array.isArray(selectedIds) ? selectedIds.filter(Boolean) : [];
  if (!ids.length || !signal) return [];
  const haystack = signalToHaystack(signal);
  if (!haystack) return [];
  return matchTopics(haystack, ids);
}
