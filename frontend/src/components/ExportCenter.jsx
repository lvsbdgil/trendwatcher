import {
  copyDigestToClipboard,
  downloadJson,
  downloadMarkdown,
  downloadPdf,
  normalizeExportData,
} from "../utils/exporters";

const { useMemo, useState } = React;

const FORMAT_LABEL = {
  markdown: "Markdown",
  pdf: "PDF",
  print: "PDF для печати",
  json: "JSON",
  copy: "текст в буфер обмена",
};

const SUCCESS_TEXT = {
  markdown: "Markdown скачан",
  pdf: "Открыт предпросмотр PDF",
  print: "Открыт предпросмотр печати",
  json: "JSON скачан",
  copy: "Текст скопирован",
};

function errorText(format, reason) {
  if (format === "copy") return "Не удалось скопировать. Скопируйте вручную.";
  if (format === "pdf" && reason === "popup_blocked") {
    return "Не удалось открыть предпросмотр PDF. Разрешите всплывающие окна.";
  }
  if (format === "pdf") return "Не удалось выполнить экспорт PDF";
  if (format === "json") return "Не удалось выполнить экспорт JSON";
  if (format === "markdown") return "Не удалось выполнить экспорт Markdown";
  return `Не удалось выполнить экспорт ${FORMAT_LABEL[format] || format}`;
}

export function ExportActions({
  result,
  signals,
  digest,
  currentUser,
  selectedWatchlistTopics,
  onTrackEvent,
  compact = false,
}) {
  const [exportStatus, setExportStatus] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  const [busyFormat, setBusyFormat] = useState(null);

  const exportData = useMemo(
    () =>
      normalizeExportData(result, signals, {
        currentUser,
        selectedWatchlistTopics,
        digest,
      }),
    [result, signals, currentUser, selectedWatchlistTopics, digest],
  );

  // Без результата компонент не показываем.
  if (!result) return null;

  const hasSignals = exportData.signalCount > 0;
  const hasDigest = Boolean(exportData.digest && exportData.digest.trim());

  function track(format, extra = {}) {
    if (typeof onTrackEvent !== "function") return;
    try {
      onTrackEvent({
        action: format === "copy" ? "copy_digest" : `export_${format}`,
        mode: "export",
        feature: "export_center",
        metadata: {
          feature: "export_center",
          signalCount: exportData.signalCount,
          format,
          ...extra,
        },
      });
    } catch {
      /* analytics никогда не блокирует UI */
    }
  }

  async function runExport(format) {
    switch (format) {
      case "markdown":
        return downloadMarkdown(exportData);
      case "pdf":
      case "print":
        return downloadPdf(exportData);
      case "json":
        return downloadJson(exportData);
      case "copy":
        return copyDigestToClipboard(exportData);
      default:
        throw new Error(`Unknown export format: ${format}`);
    }
  }

  async function handleExport(format) {
    if (isExporting) return;
    setIsExporting(true);
    setBusyFormat(format);
    setExportStatus(null);

    try {
      const outcome = await runExport(format);
      const mode = outcome?.mode || "downloaded";

      if (mode === "blocked") {
        const reason = format === "pdf" || format === "print" ? "popup_blocked" : undefined;
        setExportStatus({ type: "error", format, text: errorText("pdf", reason) });
        return;
      }

      const key = format === "copy" ? "copy" : format;

      setExportStatus({ type: "ok", format, text: SUCCESS_TEXT[key] || "Готово" });
      track(format, { mode });
    } catch (error) {
      // Явная диагностика в консоли — теперь видно, какой формат упал и почему.
      // eslint-disable-next-line no-console
      console.error("[ExportCenter] export failed", format, error);
      setExportStatus({ type: "error", format, text: errorText(format, error?.code === "POPUP_BLOCKED" ? "popup_blocked" : undefined) });
    } finally {
      setIsExporting(false);
      setBusyFormat(null);
    }
  }

  return (
    <>
      <div className={`export-center-actions${compact ? " export-center-actions-compact" : ""}`}>
        <button
          type="button"
          className="export-button"
          onClick={() => handleExport("markdown")}
          disabled={isExporting}
        >
          Markdown
        </button>
        <button
          type="button"
          className="export-button"
          onClick={() => handleExport("pdf")}
          disabled={isExporting}
        >
          Скачать PDF
        </button>
        <button
          type="button"
          className="export-button"
          onClick={() => handleExport("print")}
          disabled={isExporting}
        >
          Печать PDF
        </button>
        <button
          type="button"
          className="export-button"
          onClick={() => handleExport("json")}
          disabled={isExporting}
        >
          JSON
        </button>
        <button
          type="button"
          className="export-button"
          onClick={() => handleExport("copy")}
          disabled={isExporting || (!hasSignals && !hasDigest)}
        >
          Скопировать в буфер обмена
        </button>
      </div>

      {isExporting && busyFormat && (
        <div className="export-status export-status-busy" role="status">
          Готовим {FORMAT_LABEL[busyFormat] || busyFormat}…
        </div>
      )}

      {!isExporting && exportStatus && (
        <div
          className={`export-status ${exportStatus.type === "error" ? "export-status-error" : "export-status-ok"}`}
          role="status"
        >
          {exportStatus.text}
        </div>
      )}
    </>
  );
}

export default function ExportCenter({
  result,
  signals,
  digest,
  currentUser,
  selectedWatchlistTopics,
  onTrackEvent,
}) {
  const exportData = useMemo(
    () =>
      normalizeExportData(result, signals, {
        currentUser,
        selectedWatchlistTopics,
        digest,
      }),
    [result, signals, currentUser, selectedWatchlistTopics, digest],
  );

  if (!result) return null;

  return (
    <section className="export-section" aria-labelledby="export-center-title">
      <div className="export-center export-card">
      <header className="export-center-header">
        <div>
          <div className="export-format-chip">Export Center</div>
          <h3 className="export-center-title" id="export-center-title">
            Export Center
          </h3>
          <p className="export-center-subtitle">
            Сохраните результат анализа в формате для команды, презентации
            или дальнейшей обработки.
          </p>
        </div>
        <div className="export-meta">
          <span>{exportData.signalCount} сигналов</span>
          {exportData.selectedWatchlistTopics.length > 0 && (
            <span>watchlist: {exportData.selectedWatchlistTopics.length}</span>
          )}
        </div>
      </header>

      <ExportActions
        result={result}
        signals={signals}
        digest={digest}
        currentUser={currentUser}
        selectedWatchlistTopics={selectedWatchlistTopics}
        onTrackEvent={onTrackEvent}
      />

      <p className="export-hint">
        Markdown — для заметок и README. JSON — для аналитики.
        PDF — предпросмотр со скачиванием и печатью.
      </p>
      </div>
    </section>
  );
}
