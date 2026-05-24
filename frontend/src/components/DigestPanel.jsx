const DIGEST_COPY = {
  idle: "Дайджест появится после запуска анализа.",
  loading: "Формируем дайджест.",
  empty: "Дайджест не сформирован: сильные сигналы не найдены.",
  error: "Дайджест не сформирован из-за ошибки анализа.",
};

const EMPTY_TEXT = "Нет данных по этому блоку";

const BLOCKS = [
  ["summary", "Краткая выжимка"],
  ["why", "Почему это важно"],
  ["next", "Что можно сделать дальше"],
  ["sources", "Источники"],
  ["limits", "Ограничения / что требует проверки"],
];

const HEADING_MAP = [
  [/кратк|summary|выжим/i, "summary"],
  [/почему|важн|why now|why/i, "why"],
  [/дальш|next|action|рекоменд|что сделать/i, "next"],
  [/источник|sources/i, "sources"],
  [/огранич|провер|risk|limit|assumption/i, "limits"],
];

function cleanLine(value) {
  return String(value || "")
    .replace(/\\n/g, "\n")
    .replace(/\*\*/g, "")
    .replace(/[*`#]/g, "")
    .replace(/^\s*[-•]\s+/gm, "")
    .replace(/^\s*\d+[.)]\s+/gm, "")
    .replace(/[{}"]/g, "")
    .trim();
}

function cleanText(value) {
  const text = cleanLine(value)
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n");

  if (!text || text === "undefined" || text === "null") return EMPTY_TEXT;
  return text;
}

function normalizeArray(value) {
  if (Array.isArray(value)) return value.map(cleanText).filter((item) => item && item !== EMPTY_TEXT);
  const text = cleanText(value);
  if (text === EMPTY_TEXT) return [];
  return text.split("\n").map(cleanText).filter((item) => item && item !== EMPTY_TEXT);
}

function sectionKey(heading) {
  const found = HEADING_MAP.find(([re]) => re.test(heading));
  return found?.[1] || null;
}

function parseJsonDigest(value) {
  if (!value || typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;

  try {
    const parsed = JSON.parse(trimmed);
    const source = Array.isArray(parsed) ? { summary: parsed } : parsed;
    return {
      title: cleanText(source.title || source.heading || "Дайджест по сигналам"),
      blocks: {
        summary: normalizeArray(source.summary || source.short_summary || source.brief),
        why: normalizeArray(source.why || source.why_now || source.importance),
        next: normalizeArray(source.next || source.next_steps || source.actions || source.recommendations),
        sources: normalizeArray(source.sources || source.links),
        limits: normalizeArray(source.limits || source.limitations || source.risks || source.needs_check),
      },
    };
  } catch {
    return null;
  }
}

function parseMarkdownDigest(markdown) {
  const jsonDigest = parseJsonDigest(markdown);
  if (jsonDigest) return jsonDigest;

  const result = {
    title: "Дайджест по сигналам",
    blocks: { summary: [], why: [], next: [], sources: [], limits: [] },
  };

  if (!markdown) return result;

  let currentKey = "summary";
  const lines = String(markdown).split(/\r?\n/g);

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || /^[-*_]{3,}$/.test(line)) continue;

    const heading = line.match(/^#{1,6}\s+(.+)$/);
    if (heading) {
      const cleanedHeading = cleanText(heading[1]);
      const key = sectionKey(cleanedHeading);
      if (key) {
        currentKey = key;
      } else if (!result.title || result.title === "Дайджест по сигналам") {
        result.title = cleanedHeading;
      }
      continue;
    }

    const colonHeading = line.match(/^([^:]{3,80}):\s*(.*)$/);
    if (colonHeading) {
      const key = sectionKey(colonHeading[1]);
      if (key) {
        currentKey = key;
        if (colonHeading[2]) result.blocks[currentKey].push(cleanText(colonHeading[2]));
        continue;
      }
    }

    const cleaned = cleanText(line);
    if (cleaned !== EMPTY_TEXT) {
      result.blocks[currentKey].push(cleaned);
    }
  }

  return result;
}

function linkParts(text) {
  const raw = cleanLine(text);
  const markdownLink = raw.match(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/);
  if (markdownLink) return { label: markdownLink[1], url: markdownLink[2] };

  const url = raw.match(/https?:\/\/[^\s)]+/);
  if (url) {
    try {
      const parsed = new URL(url[0]);
      return { label: parsed.hostname.replace(/^www\./, ""), url: url[0] };
    } catch {
      return { label: url[0], url: url[0] };
    }
  }

  return null;
}

function DigestText({ items, sourceMode = false }) {
  const list = items?.length ? items : [EMPTY_TEXT];

  if (sourceMode) {
    return (
      <ul className="digest-src-list">
        {list.map((item, index) => {
          const link = linkParts(item);
          return (
            <li key={`${item}-${index}`}>
              {link ? (
                <a href={link.url} target="_blank" rel="noreferrer" className="digest-src-link" title={link.url}>
                  {link.label}
                </a>
              ) : (
                <span>{cleanText(item)}</span>
              )}
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <ul className="digest-bullets">
      {list.map((item, index) => (
        <li key={`${item}-${index}`}>{cleanText(item)}</li>
      ))}
    </ul>
  );
}

export default function DigestPanel({ digest, status = "idle", className = "", showDownload = true }) {
  const digestText = typeof digest === "string" ? digest.trim() : digest ? JSON.stringify(digest) : "";
  const canShow = status === "success" && digestText.length > 0;
  const displayStatus = canShow ? "success" : status === "success" ? "empty" : status;
  const parsed = canShow ? parseMarkdownDigest(digestText) : null;

  function downloadDigest() {
    if (!canShow) return;
    const blob = new Blob([digestText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trendwatcher-digest.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <aside className={`digest-panel${className ? ` ${className}` : ""}`} id="digest">
      <div className="section-heading digest-header">
        <p>Дайджест</p>
        {canShow && showDownload && (
          <button onClick={downloadDigest}>скачать текст</button>
        )}
      </div>

      {canShow && parsed ? (
        <div className="digest-ui">
          <div className="digest-title">
            <span>Заголовок дайджеста</span>
            <strong>{cleanText(parsed.title || "Дайджест по сигналам")}</strong>
          </div>
          {BLOCKS.map(([key, label]) => (
            <div key={key} className={`digest-section${key === "sources" ? " digest-sources-section" : ""}`}>
              <div className="digest-section-label">{label}</div>
              <DigestText items={parsed.blocks[key]} sourceMode={key === "sources"} />
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state digest-empty-state">
          <div className="empty-state-title">
            {displayStatus === "loading" ? "Формируем дайджест" : "Ожидание анализа"}
          </div>
          <div className="empty-state-text">
            {DIGEST_COPY[displayStatus] || DIGEST_COPY.idle}
          </div>
        </div>
      )}
    </aside>
  );
}
