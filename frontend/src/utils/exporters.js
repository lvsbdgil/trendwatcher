
/* ────────────────────────────── primitive helpers ────────────────────────────── */

function pickFirst(obj, keys) {
  if (!obj || typeof obj !== "object") return undefined;
  for (const k of keys) {
    const v = obj[k];
    if (v != null && v !== "") return v;
  }
  return undefined;
}

function todayStamp() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatHotness(v) {
  if (v == null) return "";
  const n = Number(v);
  return Number.isNaN(n) ? String(v) : String(Math.round(n));
}

function formatConfidence(v) {
  if (v == null) return "";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n <= 1 ? `${Math.round(n * 100)}%` : `${Math.round(n)}%`;
}

function safeJsonClone(value) {
  try { return JSON.parse(JSON.stringify(value)); } catch { return null; }
}

/* ────────────────────────────── meta formatters ────────────────────────────── */

const WATCHLIST_LABELS = {
  payments: "Платежи",
  bnpl: "BNPL",
  cards: "Карты",
  mobile_banking: "Мобильный банк",
  ux: "UX-механики",
  ai_banking: "AI в банкинге",
  regulation: "Регулирование",
  loyalty: "Loyalty",
  smb: "SMB banking",
  open_banking: "Open banking",
};

export function formatWatchlistTopics(topics) {
  if (!Array.isArray(topics)) return [];
  return topics
    .map((t) => {
      if (t == null) return "";
      const s = String(t).trim();
      if (!s) return "";
      // Если это уже не slug (есть кириллица или пробел) — не трогаем.
      if (/[А-Яа-яЁё]/.test(s) || /\s/.test(s)) return s;
      return WATCHLIST_LABELS[s] || s;
    })
    .filter(Boolean);
}

export function formatExportDate(value) {
  if (!value) return "—";
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatUser(value) {
  if (value == null) return "Гость";
  const v = String(value).trim();
  if (!v || v.toLowerCase() === "guest") return "Гость";
  return v;
}

/* ────────────────────────────── text cleanup ────────────────────────────── */

const NOISE_TRAIL_RE = /(?:LivePlaylist|Mix\s*\(\s*\d+\+?\s*\)|1\s*hour\s+(?:handpan|relax|sleep|music)|Nervous\s+System\s+Regulation|Streamed\s+\d+|\d+M?\s*views?\b|handpan\s+music)/i;

export function cleanScrapedText(text) {
  if (text == null) return "";
  let s = String(text);
  // Двойные/тройные слэши из плохого scrape.
  s = s.replace(/\\{2,}/g, " ");
  // Control characters.
  s = s.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, " ");
  // Зачистка повторяющихся пробелов и переносов.
  s = s.replace(/\s+/g, " ").trim();
  // Обрезаем мусорный хвост (плейлист/видео-метки), если он не в самом начале.
  const m = s.match(NOISE_TRAIL_RE);
  if (m && m.index != null && m.index > 60) {
    s = s.slice(0, m.index).trim().replace(/[\s\-–·,;:]+$/, "");
  }
  return s;
}

export function truncateText(text, maxLength = 700) {
  const s = String(text ?? "").trim();
  if (!s) return "";
  if (s.length <= maxLength) return s;
  const cut = s.slice(0, maxLength);
  const boundary = Math.max(
    cut.lastIndexOf(". "),
    cut.lastIndexOf("! "),
    cut.lastIndexOf("? "),
    cut.lastIndexOf("… "),
  );
  if (boundary > maxLength * 0.55) return cut.slice(0, boundary + 1).trim() + " …";
  const space = cut.lastIndexOf(" ");
  if (space > maxLength * 0.7) return cut.slice(0, space).trim() + " …";
  return cut.trim() + "…";
}

/* ────────────────────────────── source classification ────────────────────────────── */

const VIDEO_HOSTS = /(?:^|\.)(?:youtube\.com|youtu\.be|rutube\.ru|vimeo\.com|tiktok\.com|dzen\.ru\/video)$/i;
const PRIMARY_HOSTS = /(?:^|\.)(?:cbr\.ru|ecb\.europa\.eu|sec\.gov|cftc\.gov|fdic\.gov|fca\.org\.uk|bis\.org|imf\.org|government\.ru|consilium\.europa\.eu|bankofengland\.co\.uk|federalreserve\.gov)$/i;
const MEDIA_HOSTS = /(?:^|\.)(?:banki\.ru|rbc\.ru|vc\.ru|kommersant\.ru|interfax\.ru|tass\.ru|forbes\.ru|frankmedia\.ru|frankrg\.com|reuters\.com|bloomberg\.com|ft\.com|wsj\.com|theverge\.com|techcrunch\.com|finextra\.com|cnbc\.com|coindesk\.com|paymentsdive\.com|americanbanker\.com|fintechfutures\.com|cbonds\.ru)$/i;

export function hostnameOf(url) {
  if (!url) return "";
  try {
    return new URL(url).hostname.replace(/^www\./, "").toLowerCase();
  } catch { return ""; }
}

export function classifySource(src) {
  const url = src?.url || "";
  const kind = String(src?.kind || "").toLowerCase();
  if (kind === "primary") return "Primary";
  if (kind === "trusted_media") return "Media";
  const host = hostnameOf(url);
  if (VIDEO_HOSTS.test(host)) return "Video";
  if (PRIMARY_HOSTS.test(host)) return "Primary";
  if (MEDIA_HOSTS.test(host)) return "Media";
  if (kind === "reprint") return "Reprint";
  return "Unknown";
}

export function formatSourceLabel(src) {
  const titleRaw = String(src?.title || "").trim();
  const url = String(src?.url || "");
  const host = hostnameOf(url);
  const titleLower = titleRaw.toLowerCase();

  // unknown / unknown: <domain> / совпадает с URL/доменом — выкидываем title.
  const isBadTitle =
    !titleRaw ||
    titleLower === "unknown" ||
    titleLower === "unknown source" ||
    titleLower.startsWith("unknown:") ||
    titleLower.startsWith("unknown ") ||
    titleLower === host ||
    titleLower === url.toLowerCase();
  if (isBadTitle) return host || url || "—";
  return titleRaw;
}

/* ────────────────────────────── digest cleanup ────────────────────────────── */

const MD_HEADER_RE = /^(#+)\s+/;
const MD_BULLET_RE = /^(\s*)([>*+\-]|\d+[.)])\s+/;
const SECTION_RECAP_RE = /^(#+)?\s*(top\s+signals|top\s+insights|главные\s+сигналы|топ[-\s]*сигналы)\b/i;

export function normalizeDigestForReport(digest, signals = []) {
  if (!digest || typeof digest !== "string") return [];
  const headlines = (signals || [])
    .map((s) => String(s?.headline || s?.title || "").trim().toLowerCase())
    .filter(Boolean);

  const rawLines = digest.split(/\r?\n/).map((l) => l.trim());

  // Обрезаем хвост, если начался блок "Top signals/Главные сигналы" —
  // он дублирует то, что и так есть в карточках ниже.
  let cutAt = rawLines.findIndex((l) => SECTION_RECAP_RE.test(l));
  if (cutAt >= 0) rawLines.length = cutAt;

  const bullets = [];
  for (const raw of rawLines) {
    if (!raw) continue;
    if (MD_HEADER_RE.test(raw)) continue;
    let s = raw.replace(MD_BULLET_RE, "").trim();
    s = s.replace(/^\*\*([^*]+)\*\*\s*[:.]?\s*/, "$1: ");
    s = s.replace(/\*\*/g, "").replace(/`+/g, "").replace(/_+/g, " ");
    s = s.replace(/\s+/g, " ").trim();
    if (s.length < 8) continue;

    const sLow = s.replace(/[:.\s]+$/, "").toLowerCase();
    const isDupOfSignal = headlines.some((h) => {
      if (!h) return false;
      if (sLow === h) return true;
      if (sLow.startsWith(h)) return true;
      // если строка дайджеста — это headline + краткое продолжение
      const prefix = h.slice(0, Math.max(20, Math.floor(h.length * 0.7)));
      return prefix.length > 12 && sLow.startsWith(prefix);
    });
    if (isDupOfSignal) continue;

    bullets.push(truncateText(s, 220));
    if (bullets.length >= 5) break;
  }

  if (bullets.length === 0) {
    const plain = rawLines.join(" ")
      .replace(/[#*_`]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (plain) return [truncateText(plain, 700)];
  }
  return bullets;
}

/* ────────────────────────────── signal quality ────────────────────────────── */

const NOISE_PATTERNS = [
  /LivePlaylist/i,
  /\bMix\s*\(\s*\d+\+?\s*\)/i,
  /\bStreamed\s+\d+/i,
  /\b\d+M?\s*views\b/i,
  /Nervous\s+System\s+Regulation/i,
  /(handpan|relax|sleep)\s+music/i,
  /\b1\s*hour\b[^.]{0,40}\b(music|relax|handpan|sleep)\b/i,
];

const OLD_YEAR_RE = /\b(2017|2018|2019)\b/;
const RECENT_YEAR_RE = /\b(202[3-9]|20[3-9]\d)\b/;

function looksLikeRawScrape(text) {
  if (!text) return false;
  const s = String(text);
  if (s.length < 800) return false;
  const newlineDensity = (s.match(/\n/g) || []).length / Math.max(1, s.length);
  const punctDensity = (s.match(/[.!?]/g) || []).length / Math.max(1, s.length);
  return newlineDensity > 0.02 || punctDensity < 0.003;
}

export function assessSignalQuality(signal) {
  const reasons = [];
  let status = "ok";
  const promote = (lvl, reason) => {
    if (lvl === "noise" && status !== "noise") status = "noise";
    else if (lvl === "warning" && status === "ok") status = "warning";
    if (reason && !reasons.includes(reason)) reasons.push(reason);
  };

  const text = [
    signal?.headline, signal?.title,
    signal?.summary, signal?.whyNow, signal?.why_now,
    signal?.draft, signal?.evidence,
  ].filter(Boolean).map(String).join(" \n ");

  for (const re of NOISE_PATTERNS) {
    if (re.test(text)) { promote("noise", "Похоже на видео-плейлист или мусорный scrape"); break; }
  }

  const srcs = Array.isArray(signal?.sources) ? signal.sources : [];
  const isAllVideo = srcs.length > 0 && srcs.every((s) => VIDEO_HOSTS.test(hostnameOf(s?.url || "")));
  if (isAllVideo) {
    promote("warning", "Источник — YouTube, требует ручной проверки");
  }
  if (srcs.length === 0) {
    promote("warning", "Нет источников");
  } else if (srcs.every((s) => !s?.url)) {
    promote("warning", "У источников нет URL");
  }
  if (srcs.some((s) => String(s?.title || "").trim().toLowerCase() === "unknown")) {
    promote("warning", "Источник помечен как unknown");
  }

  const c = signal?.confidence;
  if (c != null) {
    const num = Number(c);
    if (!Number.isNaN(num)) {
      const pct = num <= 1 ? num * 100 : num;
      if (pct < 60) promote("warning", `Низкая confidence (${Math.round(pct)}%)`);
    }
  }

  const ev = String(signal?.evidence ?? "").trim();
  if (!ev || ev.length < 20) {
    promote("warning", "Evidence пустой или слишком короткий");
  }

  if (OLD_YEAR_RE.test(text) && !RECENT_YEAR_RE.test(text)) {
    promote("warning", "Материал упоминает только старые годы (2017–2019)");
  }

  if (looksLikeRawScrape(signal?.summary) || looksLikeRawScrape(signal?.whyNow)) {
    promote("warning", "Похоже на сырой scraped text");
  }

  return { status, reasons };
}

/* ────────────────────────────── sources / category normalize ────────────────────────────── */

function normalizeSources(value) {
  if (value == null || value === "") return [];

  if (typeof value === "string") {
    const isUrl = /^https?:\/\//i.test(value);
    return [{ title: value, url: isUrl ? value : "", kind: "" }];
  }

  if (Array.isArray(value)) {
    return value
      .map((s) => {
        if (s == null) return null;
        if (typeof s === "string") {
          const isUrl = /^https?:\/\//i.test(s);
          return { title: s, url: isUrl ? s : "", kind: "" };
        }
        if (typeof s === "object") {
          const url = s.url || s.href || s.link || "";
          const kind = String(s.kind || "");
          const title = s.title || s.name || s.source || url || "";
          return { title: String(title || ""), url: String(url || ""), kind };
        }
        return { title: String(s), url: "", kind: "" };
      })
      .filter((x) => x && (x.title || x.url));
  }

  if (typeof value === "object") {
    const url = value.url || value.href || value.link || "";
    const kind = String(value.kind || "");
    const title = value.title || value.name || value.source || url || "";
    if (!url && !title) return [];
    return [{ title: String(title || ""), url: String(url || ""), kind }];
  }

  return [];
}

function normalizeCategory(value) {
  if (value == null || value === "") return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.filter(Boolean).join(", ");
  return String(value);
}

/* ──────────────────────── universal blob download ──────────────────────── */

export function downloadBlob(content, filename, mimeType) {
  if (typeof document === "undefined" || typeof URL === "undefined") {
    throw new Error("downloadBlob: document/URL unavailable");
  }
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 0);
  return true;
}

/* ────────────────────────── data normalization ────────────────────────── */

export function normalizeExportData(result, signals, options = {}) {
  const { currentUser, selectedWatchlistTopics, digest } = options;

  let list = Array.isArray(signals) ? signals : null;
  if (!list && result && typeof result === "object") {
    list =
      (Array.isArray(result.signals) && result.signals) ||
      (Array.isArray(result.cards) && result.cards) ||
      (Array.isArray(result.items) && result.items) ||
      (Array.isArray(result.digest?.signals) && result.digest.signals) ||
      [];
  }
  if (!Array.isArray(list)) list = [];

  const digestText =
    (digest && String(digest)) ||
    (typeof result?.digest === "string" ? result.digest : "") ||
    "";

  const normalizedSignals = list.map((s) => {
    const headline = pickFirst(s, ["headline", "title", "name"]) || "Без заголовка";
    const hotness = pickFirst(s, ["hotness", "importance", "score", "rating"]);
    const confidence = pickFirst(s, ["confidence", "confidence_score", "certainty"]);
    const category = normalizeCategory(pickFirst(s, ["category", "type", "tags"]));
    const whyNow = pickFirst(s, ["whyNow", "why_now", "reason", "importance_reason"]) || "";
    const summary = pickFirst(s, ["summary", "description", "short_summary"]) || "";
    const draft = pickFirst(s, ["draft", "post_draft", "team_note"]) || "";
    const evidence = pickFirst(s, ["evidence"]) || "";
    const sources = normalizeSources(pickFirst(s, ["sources", "links", "urls", "source"]));
    const matchedTopics = Array.isArray(s?.matchedTopics) ? s.matchedTopics : [];

    const normalized = {
      headline: String(headline),
      hotness: hotness != null ? hotness : null,
      confidence: confidence != null ? confidence : null,
      category,
      matchedTopics,
      whyNow: cleanScrapedText(whyNow),
      summary: cleanScrapedText(summary),
      draft: cleanScrapedText(draft),
      evidence: cleanScrapedText(evidence),
      sources,
      raw: safeJsonClone(s),
    };
    normalized.quality = assessSignalQuality(normalized);
    return normalized;
  });

  const exportedAtDate = new Date();
  return {
    exportedAt: exportedAtDate.toISOString(),
    exportedAtFormatted: formatExportDate(exportedAtDate),
    user: currentUser?.username || "",
    userFormatted: formatUser(currentUser?.username),
    signalCount: normalizedSignals.length,
    selectedWatchlistTopics: Array.isArray(selectedWatchlistTopics) ? selectedWatchlistTopics : [],
    selectedWatchlistTopicsFormatted: formatWatchlistTopics(selectedWatchlistTopics),
    digest: String(digestText || ""),
    digestBullets: normalizeDigestForReport(digestText, normalizedSignals),
    signals: normalizedSignals,
  };
}

function bucketSignals(signals) {
  const ok = [];
  const warning = [];
  const noise = [];
  for (const s of signals || []) {
    const status = s?.quality?.status || "ok";
    if (status === "noise") noise.push(s);
    else if (status === "warning") warning.push(s);
    else ok.push(s);
  }
  return { ok, warning, noise };
}

const LIMITATIONS_TEXT =
  "Дайджест собран по открытым источникам. Перед продуктовым решением нужно проверить первоисточник, владельца продукта и затронутую метрику.";

/* ────────────────────────────── Markdown ────────────────────────────── */

export function downloadMarkdown(exportData) {
  const lines = [];
  lines.push("# TrendWatcher Digest");
  lines.push("");
  lines.push(`- Дата экспорта: ${exportData.exportedAtFormatted}`);
  lines.push(`- Пользователь: ${exportData.userFormatted}`);
  lines.push(`- Сигналов: ${exportData.signalCount}`);
  if (exportData.selectedWatchlistTopicsFormatted.length) {
    lines.push(`- Watchlist: ${exportData.selectedWatchlistTopicsFormatted.join(", ")}`);
  }
  lines.push("");

  if (exportData.digestBullets.length) {
    lines.push("## Короткий дайджест");
    lines.push("");
    exportData.digestBullets.forEach((b) => lines.push(`- ${b}`));
    lines.push("");
  }

  const { ok, warning, noise } = bucketSignals(exportData.signals);

  const writeSignal = (s, i) => {
    lines.push(`### ${i + 1}. ${s.headline}`);
    const hotness = formatHotness(s.hotness);
    const confidence = formatConfidence(s.confidence);
    if (hotness) lines.push(`- Hotness: ${hotness}`);
    if (confidence) lines.push(`- Confidence: ${confidence}`);
    if (s.category) lines.push(`- Category: ${s.category}`);
    if (s.matchedTopics.length) {
      lines.push(`- Watchlist: ${formatWatchlistTopics(s.matchedTopics).join(", ")}`);
    }
    if (s.quality?.reasons?.length) {
      lines.push(`- Проверка: ${s.quality.reasons.join("; ")}`);
    }
    if (s.whyNow) { lines.push(""); lines.push(`**Why now:** ${truncateText(s.whyNow, 700)}`); }
    if (s.summary) { lines.push(""); lines.push(`**Summary:** ${truncateText(s.summary, 900)}`); }
    if (s.draft) { lines.push(""); lines.push(`**Draft:** ${truncateText(s.draft, 900)}`); }
    if (s.sources.length) {
      lines.push("");
      lines.push("**Sources:**");
      s.sources.forEach((src) => {
        const label = formatSourceLabel(src);
        if (src.url) lines.push(`- [${label}](${src.url}) · ${classifySource(src)}`);
        else lines.push(`- ${label} · ${classifySource(src)}`);
      });
    }
    lines.push("");
  };

  if (ok.length) {
    lines.push("## Главные сигналы");
    lines.push("");
    ok.forEach(writeSignal);
  }
  if (warning.length) {
    lines.push("## Требует проверки");
    lines.push("");
    warning.forEach(writeSignal);
  }
  if (noise.length) {
    lines.push("## Отброшено как шум");
    lines.push("");
    noise.forEach((s, i) => {
      const reason = s.quality?.reasons?.[0] || "Шум";
      lines.push(`- ${i + 1}. ${s.headline} — ${reason}`);
    });
    lines.push("");
  }
  lines.push("## Ограничения");
  lines.push("");
  lines.push(LIMITATIONS_TEXT);
  lines.push("");

  downloadBlob(
    lines.join("\n"),
    `trendwatcher-digest-${todayStamp()}.md`,
    "text/markdown;charset=utf-8",
  );
  return { mode: "downloaded" };
}

/* ────────────────────────────── JSON ────────────────────────────── */

export function downloadJson(exportData) {
  const data = {
    meta: {
      product: "BigPuzoTeam · TrendWatcher",
      exportedAt: exportData.exportedAt,
      exportedAtFormatted: exportData.exportedAtFormatted,
      user: exportData.user,
      userFormatted: exportData.userFormatted,
      signalCount: exportData.signalCount,
      selectedWatchlistTopics: exportData.selectedWatchlistTopics,
      selectedWatchlistTopicsFormatted: exportData.selectedWatchlistTopicsFormatted,
    },
    digest: exportData.digest,
    digestBullets: exportData.digestBullets,
    signals: exportData.signals.map((s) => ({
      headline: s.headline,
      hotness: s.hotness,
      confidence: s.confidence,
      category: s.category,
      matchedTopics: s.matchedTopics,
      whyNow: s.whyNow,
      summary: s.summary,
      draft: s.draft,
      evidence: s.evidence,
      sources: s.sources.map((src) => ({
        title: formatSourceLabel(src),
        url: src.url,
        kind: classifySource(src),
      })),
      quality: s.quality,
      raw: s.raw,
    })),
  };

  downloadBlob(
    JSON.stringify(data, null, 2),
    `trendwatcher-export-${todayStamp()}.json`,
    "application/json;charset=utf-8",
  );
  return { mode: "downloaded" };
}


/* ────────────────────────────── PDF preview HTML ────────────────────────────── */

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderSourceLi(src) {
  const label = escapeHtml(formatSourceLabel(src));
  const url = src?.url ? escapeHtml(src.url) : "";
  const kind = escapeHtml(classifySource(src));
  const badge = `<span class="src-kind src-kind-${kind.toLowerCase()}">${kind}</span>`;
  const tail =
    kind === "Video" || kind === "Unknown"
      ? ` <span class="src-warn">требует ручной проверки</span>`
      : "";
  if (url) {
    return `<li>${badge} <a href="${url}" target="_blank" rel="noreferrer">${label}</a>${tail}</li>`;
  }
  return `<li>${badge} ${label}${tail}</li>`;
}

function renderSignalCard(s, i, opts = {}) {
  const idx = String(i + 1).padStart(2, "0");
  const chips = [];
  if (s.hotness != null) chips.push(`<span class="chip chip-hot">Hotness · ${escapeHtml(formatHotness(s.hotness))}</span>`);
  if (s.confidence != null) chips.push(`<span class="chip chip-conf">Confidence · ${escapeHtml(formatConfidence(s.confidence))}</span>`);
  if (s.category) chips.push(`<span class="chip chip-cat">${escapeHtml(s.category)}</span>`);
  const srcKinds = new Set((s.sources || []).map((src) => classifySource(src)));
  for (const k of srcKinds) chips.push(`<span class="chip chip-src chip-src-${k.toLowerCase()}">${k}</span>`);

  const topicsRow = s.matchedTopics?.length
    ? `<div class="topic-row">${formatWatchlistTopics(s.matchedTopics)
        .map((t) => `<span class="topic-chip">${escapeHtml(t)}</span>`)
        .join("")}</div>`
    : "";

  const reasonsRow =
    opts.showReasons && s.quality?.reasons?.length
      ? `<div class="reason-row">
           <span class="reason-label">Почему отмечен:</span>
           ${s.quality.reasons.map((r) => `<span class="reason-chip">${escapeHtml(r)}</span>`).join("")}
         </div>`
      : "";

  const sourcesHtml = (s.sources || []).length
    ? `<div class="sig-sources">
         <div class="sig-sources-label">Sources</div>
         <ul>${s.sources.map(renderSourceLi).join("")}</ul>
       </div>`
    : `<div class="sig-sources sig-sources-empty">Источники не указаны</div>`;

  const why = truncateText(s.whyNow, 600);
  const summary = truncateText(s.summary, 800);
  const draft = truncateText(s.draft, 800);

  return `
    <article class="sig-card">
      <div class="sig-num">${idx}</div>
      <h3 class="sig-headline">${escapeHtml(s.headline)}</h3>
      ${chips.length ? `<div class="chip-row">${chips.join("")}</div>` : ""}
      ${topicsRow}
      ${reasonsRow}
      ${why ? `<div class="sig-field"><span class="sig-field-k">Why now</span><p>${escapeHtml(why)}</p></div>` : ""}
      ${summary ? `<div class="sig-field"><span class="sig-field-k">Summary</span><p>${escapeHtml(summary)}</p></div>` : ""}
      ${draft ? `<div class="sig-field"><span class="sig-field-k">Draft</span><p>${escapeHtml(draft)}</p></div>` : ""}
      ${sourcesHtml}
    </article>
  `;
}

function renderPreviewHtml(exportData) {
  const origin =
    typeof window !== "undefined" && window.location && window.location.origin
      ? window.location.origin
      : "";
  const logoSrc = origin ? `${origin}/logo.svg` : "";
  const brandLogo = logoSrc
    ? `<img class="brand-logo" alt="" src="${escapeHtml(logoSrc)}" onerror="this.style.display='none'" />`
    : "";

  const safeDate = escapeHtml(exportData.exportedAtFormatted);
  const safeUser = escapeHtml(exportData.userFormatted);
  const watchlist = exportData.selectedWatchlistTopicsFormatted;
  const safeWatchlist = watchlist.length ? escapeHtml(watchlist.join(", ")) : "—";

  const { ok, warning, noise } = bucketSignals(exportData.signals);

  const metricsRow = `
    <div class="hero-metrics">
      <div class="metric">
        <span class="metric-k">Сигналов</span>
        <span class="metric-v">${exportData.signalCount}</span>
      </div>
      <div class="metric">
        <span class="metric-k">Watchlist</span>
        <span class="metric-v">${watchlist.length}</span>
      </div>
      <div class="metric">
        <span class="metric-k">Дата</span>
        <span class="metric-v metric-v-date">${safeDate}</span>
      </div>
      <div class="metric">
        <span class="metric-k">Пользователь</span>
        <span class="metric-v">${safeUser}</span>
      </div>
    </div>
  `;

  const digestBlock = exportData.digestBullets.length
    ? `<ul class="digest-bullets">${exportData.digestBullets
        .map((b) => `<li>${escapeHtml(b)}</li>`)
        .join("")}</ul>`
    : `<div class="digest-empty">Дайджест не сформирован</div>`;

  const sectionOk = ok.length
    ? `<section class="section">
         <h2 class="section-title">Главные сигналы</h2>
         ${ok.map((s, i) => renderSignalCard(s, i)).join("")}
       </section>`
    : "";

  const sectionWarn = warning.length
    ? `<section class="section">
         <h2 class="section-title section-title-warn">Требует проверки</h2>
         ${warning.map((s, i) => renderSignalCard(s, i, { showReasons: true })).join("")}
       </section>`
    : "";

  const sectionNoise = noise.length
    ? `<section class="section">
         <h2 class="section-title section-title-noise">Отброшено как шум</h2>
         <ul class="noise-list">
           ${noise.map((s, i) => {
             const reason = s.quality?.reasons?.[0] || "Шум";
             return `<li><span class="noise-num">${String(i + 1).padStart(2, "0")}</span>
                       <span class="noise-headline">${escapeHtml(s.headline)}</span>
                       <span class="noise-reason">${escapeHtml(reason)}</span></li>`;
           }).join("")}
         </ul>
       </section>`
    : "";

  return `<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>TrendWatcher Digest · предпросмотр</title>
<style>
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; background: #0c1612; color: #f0f5f1;
    font-family: "Inter", -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    line-height: 1.5; font-size: 14px; min-height: 100vh;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  a { color: #7dc97f; text-decoration: none; }
  a:hover { text-decoration: underline; }

  .toolbar {
    position: sticky; top: 0; z-index: 50;
    background: rgba(12, 22, 18, 0.92);
    backdrop-filter: saturate(140%) blur(10px);
    -webkit-backdrop-filter: saturate(140%) blur(10px);
    border-bottom: 1px solid #243a32;
    padding: 12px 24px;
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  }
  .toolbar-hint {
    margin-left: auto; font-size: 12px; color: #8a9e94;
    font-family: ui-monospace, "JetBrains Mono", monospace; letter-spacing: 0.02em;
    max-width: 560px; text-align: right;
  }
  .btn {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 9px 16px; border-radius: 2px; cursor: pointer;
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 12px; font-weight: 500; letter-spacing: 0.04em;
    border: 1px solid #3a4a42; background: #161f1b; color: #f0f5f1;
    transition: background .15s, border-color .15s, color .15s;
  }
  .btn:hover { border-color: #7dc97f; color: #ffffff; }
  .btn-primary { background: #7dc97f; border-color: #7dc97f; color: #0c1612; }
  .btn-primary:hover { background: #93d695; border-color: #93d695; color: #0c1612; }

  .doc { max-width: 1100px; margin: 32px auto 64px; padding: 0 24px; }
  .doc-card {
    background: #161f1b; border: 1px solid #243a32; border-radius: 4px;
    box-shadow: 0 24px 80px -32px rgba(0,0,0,0.6);
    overflow: hidden;
  }

  .doc-head {
    padding: 28px 32px 24px; border-bottom: 1px solid #243a32;
    display: grid; grid-template-columns: 1fr auto; gap: 24px;
    align-items: start;
  }
  .brand { display: flex; align-items: center; gap: 12px; }
  .brand-logo {
    width: 36px; height: 36px; object-fit: contain;
    filter: drop-shadow(0 0 8px rgba(125, 201, 127, 0.35));
  }
  .brand-text {
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 12px; font-weight: 500; letter-spacing: 0.04em; color: #f0f5f1;
  }
  .brand-text small { display: block; color: #8a9e94; font-weight: 400; margin-top: 2px; }
  .head-right {
    text-align: right;
    font-family: ui-monospace, "JetBrains Mono", monospace; font-size: 11px;
    color: #8a9e94; line-height: 1.8; letter-spacing: 0.02em;
  }
  .head-right b { color: #bcc5be; font-weight: 500; }
  .badge {
    display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 2px;
    background: rgba(125, 201, 127, 0.1);
    border: 1px solid rgba(125, 201, 127, 0.35);
    color: #7dc97f;
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10px; font-weight: 500; letter-spacing: 0.1em;
    text-transform: uppercase; margin-top: 10px;
  }

  .hero { padding: 32px; }
  .hero-title {
    margin: 0 0 10px; font-size: 36px; line-height: 1.1; letter-spacing: -0.025em;
    font-weight: 500; color: #ffffff;
  }
  .hero-sub { margin: 0 0 22px; max-width: 64ch; font-size: 14.5px; color: #bcc5be; }
  .hero-metrics {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
    background: #243a32; border: 1px solid #243a32; border-radius: 3px; overflow: hidden;
  }
  .metric { background: #1a2520; padding: 14px 16px; }
  .metric-k {
    display: block; font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10px; font-weight: 500; letter-spacing: 0.08em;
    color: #8a9e94; text-transform: uppercase;
  }
  .metric-v {
    display: block; margin-top: 6px; font-size: 22px; font-weight: 500;
    color: #f0f5f1; letter-spacing: -0.01em; font-variant-numeric: tabular-nums;
  }
  .metric-v-date { font-size: 12px; font-family: ui-monospace, monospace; color: #bcc5be; }

  .section { padding: 24px 32px; border-top: 1px solid #243a32; }
  .section-title {
    margin: 0 0 16px;
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 11px; font-weight: 500; letter-spacing: 0.1em;
    color: #7dc97f; text-transform: uppercase;
  }
  .section-title-warn { color: #f1b07a; }
  .section-title-noise { color: #d97777; }

  .digest-bullets {
    margin: 0; padding: 14px 22px; list-style: disc;
    background: #1a2520; border: 1px solid #243a32; border-radius: 3px;
    color: #e2ebe5;
  }
  .digest-bullets li { margin: 4px 0; font-size: 14px; line-height: 1.55; }
  .digest-empty {
    padding: 14px 16px; background: #1a2520; border: 1px dashed #3a4a42;
    border-radius: 3px; color: #8a9e94; font-style: italic;
  }

  .sig-card {
    padding: 20px 22px 18px;
    background: #1a2520; border: 1px solid #243a32; border-radius: 3px;
    margin-bottom: 12px;
    break-inside: avoid; page-break-inside: avoid;
  }
  .sig-num {
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10px; font-weight: 500; letter-spacing: 0.08em;
    color: #7dc97f; text-transform: uppercase; margin-bottom: 6px;
  }
  .sig-headline {
    margin: 0 0 12px; font-size: 17px; font-weight: 500; line-height: 1.3;
    letter-spacing: -0.005em; color: #ffffff;
  }
  .chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .chip {
    display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 2px;
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 11px; font-weight: 500; letter-spacing: 0.02em;
    border: 1px solid #3a4a42; background: #161f1b; color: #bcc5be;
  }
  .chip-hot { color: #f1b07a; border-color: rgba(241, 176, 122, 0.35); background: rgba(241, 176, 122, 0.08); }
  .chip-conf { color: #7dc97f; border-color: rgba(125, 201, 127, 0.35); background: rgba(125, 201, 127, 0.08); }
  .chip-cat { color: #bcc5be; }
  .chip-src-primary { color: #7dc97f; border-color: rgba(125, 201, 127, 0.45); }
  .chip-src-media   { color: #9ec0d9; border-color: rgba(158, 192, 217, 0.45); }
  .chip-src-video   { color: #f1b07a; border-color: rgba(241, 176, 122, 0.45); }
  .chip-src-unknown,
  .chip-src-reprint { color: #bcc5be; border-color: #3a4a42; }

  .topic-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .topic-chip {
    display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 2px;
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10.5px; font-weight: 500; letter-spacing: 0.02em;
    color: #7dc97f; border: 1px dashed rgba(125, 201, 127, 0.45);
  }

  .reason-row {
    display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
    margin-bottom: 10px;
  }
  .reason-label {
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10px; font-weight: 500; letter-spacing: 0.08em;
    color: #f1b07a; text-transform: uppercase;
  }
  .reason-chip {
    display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 2px;
    font-size: 11px; color: #f1b07a;
    background: rgba(241, 176, 122, 0.08);
    border: 1px solid rgba(241, 176, 122, 0.35);
  }

  .sig-field { margin-top: 10px; }
  .sig-field-k {
    display: inline-block; margin-bottom: 4px;
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10px; font-weight: 500; letter-spacing: 0.08em;
    color: #8a9e94; text-transform: uppercase;
  }
  .sig-field p { margin: 0; font-size: 13.5px; line-height: 1.55; color: #e2ebe5; }

  .sig-sources { margin-top: 14px; padding-top: 12px; border-top: 1px dashed #243a32; }
  .sig-sources-label {
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10px; font-weight: 500; letter-spacing: 0.08em;
    color: #8a9e94; text-transform: uppercase; margin-bottom: 6px;
  }
  .sig-sources ul { margin: 0; padding-left: 0; list-style: none; font-size: 12.5px; line-height: 1.7; }
  .sig-sources li { padding: 2px 0; }
  .src-kind {
    display: inline-flex; align-items: center; padding: 1px 7px;
    border-radius: 2px; font-size: 10px; font-weight: 500;
    font-family: ui-monospace, "JetBrains Mono", monospace; letter-spacing: 0.04em;
    margin-right: 6px;
    border: 1px solid #3a4a42; color: #bcc5be; background: #0f1816;
  }
  .src-kind-primary { color: #7dc97f; border-color: rgba(125, 201, 127, 0.45); }
  .src-kind-media   { color: #9ec0d9; border-color: rgba(158, 192, 217, 0.45); }
  .src-kind-video   { color: #f1b07a; border-color: rgba(241, 176, 122, 0.45); }
  .src-warn {
    margin-left: 6px; font-size: 10.5px; color: #d99b6a;
    font-family: ui-monospace, "JetBrains Mono", monospace;
  }
  .sig-sources-empty { color: #8a9e94; font-style: italic; font-size: 12.5px; }

  .noise-list { list-style: none; padding: 0; margin: 0; }
  .noise-list li {
    display: grid; grid-template-columns: 36px 1fr auto; gap: 12px;
    padding: 10px 14px; border: 1px solid #2a3530; border-radius: 3px;
    background: #16201c; margin-bottom: 8px; align-items: baseline;
    font-size: 13px;
  }
  .noise-num {
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10.5px; color: #8a9e94; letter-spacing: 0.06em;
  }
  .noise-headline { color: #d5ddd8; }
  .noise-reason {
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10.5px; color: #d97777; letter-spacing: 0.02em;
  }

  .limits-card {
    padding: 14px 18px; background: #1a2520;
    border: 1px solid #243a32; border-radius: 3px;
    color: #bcc5be; font-size: 13px; line-height: 1.55;
  }

  .doc-foot {
    padding: 20px 32px; border-top: 1px solid #243a32;
    display: flex; justify-content: space-between; align-items: center;
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 10.5px; letter-spacing: 0.06em; text-transform: uppercase;
    color: #6f8479; flex-wrap: wrap; gap: 12px;
  }
  .doc-foot small { font-size: 9.5px; color: #51625a; text-transform: none; letter-spacing: 0.02em; }

  @media (max-width: 760px) {
    .doc { padding: 0 12px; margin: 16px auto 40px; }
    .doc-head { grid-template-columns: 1fr; padding: 22px 20px; }
    .head-right { text-align: left; }
    .hero { padding: 22px 20px; }
    .hero-title { font-size: 26px; }
    .hero-metrics { grid-template-columns: 1fr 1fr; }
    .section { padding: 18px 20px; }
    .doc-foot { padding: 16px 20px; }
    .toolbar { padding: 10px 14px; }
    .toolbar-hint { display: none; }
    .noise-list li { grid-template-columns: 28px 1fr; }
    .noise-reason { grid-column: 1 / -1; }
  }

  @page { margin: 12mm; }
  @media print {
    * {
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    .toolbar { display: none !important; }
    .doc { max-width: none !important; margin: 0 !important; padding: 0 !important; }
    .doc-card { box-shadow: none !important; }
    .sig-card { page-break-inside: avoid; break-inside: avoid; }
    .noise-list li { page-break-inside: avoid; }
    .limits-card { page-break-inside: avoid; }
  }
</style>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js"></script>
</head>
<body>
  <div class="toolbar" role="toolbar" aria-label="Действия">
    <button class="btn btn-primary" type="button" id="btn-download">Скачать PDF</button>
    <button class="btn" type="button" id="btn-close">Закрыть</button>
  </div>

  <div class="doc">
    <article class="doc-card">
      <header class="doc-head">
        <div>
          <div class="brand">
            ${brandLogo}
            <div class="brand-text">BigPuzoTeam<small>TrendWatcher</small></div>
          </div>
          <span class="badge">Fintech Signal Digest</span>
        </div>
        <div class="head-right">
          <b>Дата экспорта</b> · ${safeDate}<br />
          <b>Пользователь</b> · ${safeUser}<br />
          <b>Сигналов</b> · ${exportData.signalCount}<br />
          <b>Watchlist</b> · ${safeWatchlist}
        </div>
      </header>

      <section class="hero">
        <h1 class="hero-title">TrendWatcher Digest</h1>
        <p class="hero-sub">
          Отобранные финтех-сигналы, важность, источники и краткая выжимка для команды.
        </p>
        ${metricsRow}
      </section>

      <section class="section">
        <h2 class="section-title">Короткий дайджест</h2>
        ${digestBlock}
      </section>

      ${sectionOk}
      ${sectionWarn}
      ${sectionNoise}

      <section class="section">
        <h2 class="section-title">Ограничения</h2>
        <div class="limits-card">${escapeHtml(LIMITATIONS_TEXT)}</div>
      </section>

      <footer class="doc-foot">
        <span>Generated by BigPuzoTeam · TrendWatcher</span>
        <small>Prototype for fintech publications monitoring</small>
      </footer>
    </article>
  </div>

  <script>
    (function () {
      var filename = ${JSON.stringify(`trendwatcher-digest-${todayStamp()}.pdf`)};
      var btnDownload = document.getElementById("btn-download");
      var btnClose = document.getElementById("btn-close");

      if (btnDownload) btnDownload.addEventListener("click", async function () {
        var h2c = typeof window.html2canvas === "function" ? window.html2canvas : null;
        var jspdf = window.jspdf;
        if (!h2c || !jspdf) {
          // CDN not loaded yet — fall back to print dialog
          try { window.focus(); window.print(); } catch (e) {}
          return;
        }
        btnDownload.disabled = true;
        btnDownload.textContent = "Генерируем…";
        try {
          var target = document.querySelector(".doc-card") || document.body;
          var canvas = await h2c(target, {
            scale: 1.5,
            backgroundColor: "#0c1612",
            useCORS: true,
            logging: false,
          });
          var imgData = canvas.toDataURL("image/jpeg", 0.92);
          var { jsPDF } = jspdf;
          var W = 210, H = 297;
          var ratio = canvas.height / canvas.width;
          var imgH = W * ratio;
          var pdf = new jsPDF("p", "mm", "a4");
          var pos = 0, left = imgH;
          pdf.addImage(imgData, "JPEG", 0, pos, W, imgH);
          left -= H;
          while (left > 0) {
            pos -= H;
            pdf.addPage();
            pdf.addImage(imgData, "JPEG", 0, pos, W, imgH);
            left -= H;
          }
          pdf.save(filename);
        } catch (e) {
          console.error("[pdf-preview] html2canvas failed", e);
          try { window.focus(); window.print(); } catch (_) {}
        } finally {
          btnDownload.disabled = false;
          btnDownload.textContent = "Скачать PDF";
        }
      });

      if (btnClose) btnClose.addEventListener("click", function () {
        try { window.close(); } catch (e) {}
      });
    })();
  </script>
</body>
</html>`;
}


/**
 * Открыть HTML-страницу предпросмотра PDF в новой вкладке.
 * Печать НЕ запускается автоматически — пользователь сам нажимает кнопку.
 *
 * Намеренно НЕ используем `noopener` в window.open — браузеры с этим
 * флагом возвращают `null`, даже если попап реально открыт.
 *
 * Бросает Error("POPUP_BLOCKED"), если попап заблокирован.
 */
export function openPdfPreviewFallback(exportData) {
  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    const err = new Error("POPUP_BLOCKED");
    err.code = "POPUP_BLOCKED";
    throw err;
  }
  const html = renderPreviewHtml(exportData);
  printWindow.document.open();
  printWindow.document.write(html);
  printWindow.document.close();
  try { printWindow.focus(); } catch { /* ignore */ }
}

export function downloadPdf(exportData) {
  try {
    openPdfPreviewFallback(exportData);
    return { mode: "preview" };
  } catch (err) {
    if (err?.code === "POPUP_BLOCKED") return { mode: "blocked" };
    throw err;
  }
}

/* ────────────────────────────── Copy to clipboard ────────────────────────────── */

export async function copyDigestToClipboard(exportData) {
  const top = (bucketSignals(exportData.signals).ok || []).slice(0, 5);
  const lines = [];
  lines.push("TrendWatcher · краткий дайджест");
  lines.push("");
  lines.push(`Найдено сигналов: ${exportData.signalCount}`);
  if (top.length) lines.push("");

  top.forEach((s, i) => {
    const hot = formatHotness(s.hotness);
    lines.push(`${i + 1}. ${s.headline}${hot ? ` · hotness ${hot}` : ""}`);
    if (s.whyNow) lines.push(`   Why now: ${truncateText(s.whyNow, 240)}`);
  });

  if (top.length) lines.push("");
  lines.push("Полный дайджест доступен в экспорте.");
  const text = lines.join("\n");

  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return { mode: "copied" };
    }
  } catch { /* fallthrough */ }

  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok ? { mode: "copied" } : { mode: "blocked" };
  } catch {
    return { mode: "blocked" };
  }
}
