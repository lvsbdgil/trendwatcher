import {
  analyzeArticles,
  analyzeSample,
  ApiError,
  AuthRequiredError,
  crawlFirecrawlSources,
  fetchMe,
  logout as apiLogout,
  scrapeFirecrawlUrls,
  searchFirecrawl,
  trackEvent,
} from "./api";
import AboutPage from "./components/AboutPage";
import Header from "./components/Header";
import LoginModal from "./components/LoginModal";
import ProfilePage from "./components/ProfilePage";
import DigestPage from "./components/DigestPage";
import FirecrawlPanel from "./components/FirecrawlPanel";
import SearchProgress from "./components/SearchProgress";
import PipelineSteps from "./components/PipelineSteps";
import StatsBar from "./components/StatsBar";
import SignalCard from "./components/SignalCard";
import SourceTable from "./components/SourceTable";
import WatchlistPanel from "./components/WatchlistPanel";
import { DEFAULT_WATCHLIST, WATCHLIST_TOPICS, getMatchedTopics } from "./utils/watchlist";
import { digestMetrics } from "./utils/resultMetrics";

const { useEffect, useMemo, useRef, useState } = React;

const WATCHLIST_KEY_PREFIX = "trendwatcher.watchlist.";
const VALID_TOPIC_IDS = new Set(WATCHLIST_TOPICS.map((t) => t.id));

function watchlistStorageKey(user) {
  const name = user?.username ? String(user.username) : "guest";
  return `${WATCHLIST_KEY_PREFIX}${name}`;
}

function loadWatchlist(key) {
  if (typeof window === "undefined") return DEFAULT_WATCHLIST;
  try {
    const raw = window.localStorage.getItem(key);
    if (raw == null) return DEFAULT_WATCHLIST;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return DEFAULT_WATCHLIST;
    const cleaned = parsed.filter((id) => VALID_TOPIC_IDS.has(id));
    return cleaned;
  } catch {
    return DEFAULT_WATCHLIST;
  }
}

function saveWatchlist(key, topics) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(topics));
  } catch {
    /* localStorage недоступен — молча игнорируем */
  }
}

const PAGE_TITLE = "BigPuzoTeam · TrendWatcher";
const ERROR_TEXT = "Не удалось завершить анализ. Проверьте входные данные или попробуйте демо-пример.";

const DEV_MODE = import.meta.env.DEV;

function scrollTo(id) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

const ERROR_MESSAGES = {
  FIRECRAWL_API_KEY_MISSING: "Сервис поиска временно недоступен.",
  FIRECRAWL_AUTH_FAILED: "Не удалось подключиться к сервису поиска.",
  FIRECRAWL_RATE_LIMIT: "Сервис поиска перегружен — слишком много запросов.",
  FIRECRAWL_REQUEST_FAILED: "Поиск не удался. Проверьте запрос или попробуйте позже.",
  NO_URLS_FOUND: "По запросу ничего не найдено.",
  EXTRACTION_FAILED: "Не удалось загрузить содержимое страниц по ссылкам.",
  NO_VALID_ARTICLES: "После фильтрации не осталось подходящих материалов.",
  LLM_API_KEY_MISSING: "ИИ-анализ недоступен, использован базовый режим.",
  LLM_REQUEST_FAILED: "Сервис ИИ-анализа не ответил, использован базовый режим.",
  LLM_JSON_PARSE_FAILED: "Получен неожиданный ответ от ИИ, использован базовый режим.",
  SCORING_FAILED: "Не удалось рассчитать оценки важности.",
  AUTH_REQUIRED: "Для этой функции нужен аккаунт.",
  VALIDATION_ERROR: "Неверный формат данных.",
  UNKNOWN_ERROR: ERROR_TEXT,
  NETWORK_ERROR: "Нет связи с сервером.",
};

const ERROR_HINTS = {
  FIRECRAWL_API_KEY_MISSING: "Обратитесь к администратору системы.",
  FIRECRAWL_AUTH_FAILED: "Обратитесь к администратору системы.",
  FIRECRAWL_RATE_LIMIT: "Подождите 1–2 минуты и попробуйте снова.",
  FIRECRAWL_REQUEST_FAILED: "Попробуйте изменить формулировку запроса или тему поиска.",
  NO_URLS_FOUND: "Попробуйте более конкретный запрос, например: «ипотека ставки 2024».",
  EXTRACTION_FAILED: "Убедитесь, что ссылки ведут на публичные статьи без paywall.",
  NO_VALID_ARTICLES: "Попробуйте добавить больше источников или расширить тему.",
  LLM_API_KEY_MISSING: "Результаты могут быть менее точными.",
  LLM_REQUEST_FAILED: "Результаты могут быть менее точными.",
  LLM_JSON_PARSE_FAILED: "Результаты могут быть менее точными.",
  AUTH_REQUIRED: "Войдите или создайте аккаунт — это бесплатно.",
  VALIDATION_ERROR: "Проверьте, что ссылки начинаются с https:// и текст не пустой.",
  NETWORK_ERROR: "Проверьте подключение к интернету или обновите страницу.",
  UNKNOWN_ERROR: "Если проблема повторяется — запустите демо-пример.",
};

const STEP_LABELS = {
  firecrawl_search: "сбор публикаций через Firecrawl",
  firecrawl_scrape: "загрузка страниц через Firecrawl",
  firecrawl_crawl: "обход источников через Firecrawl",
  extract_articles: "извлечение статей",
  filter_noise: "фильтр шума и релевантности",
  llm_analysis: "анализ через LLM",
  deduplicate: "дедупликация сигналов",
  scoring: "скоринг важности и confidence",
  build_cards: "сборка карточек",
  build_digest: "сборка дайджеста",
  response: "финальная сборка ответа",
};

function humanStepLabel(error) {
  if (!error || typeof error !== "object") return "—";
  if (error.stepName && STEP_LABELS[error.stepName]) return STEP_LABELS[error.stepName];
  if (error.stepName) return error.stepName;
  if (error.step != null) return `шаг ${error.step}`;
  return "—";
}

function normalizeError(err, fallback = ERROR_TEXT, step = null) {
  if (err instanceof ApiError || err instanceof AuthRequiredError) {
    return {
      code: err.code || "UNKNOWN_ERROR",
      message: ERROR_MESSAGES[err.code] || err.message || fallback,
      technicalMessage: err.message || "",
      requestId: err.requestId || null,
      step: err.step || step,
      stepName: err.stepName || null,
      details: err.details || null,
    };
  }
  if (typeof err === "string") {
    return { code: "CLIENT_ERROR", message: err, technicalMessage: err, step, stepName: null };
  }
  if (err && typeof err === "object" && err.code) {
    return {
      code: err.code,
      message: ERROR_MESSAGES[err.code] || err.message || fallback,
      technicalMessage: err.message || "",
      requestId: err.requestId || err.request_id || null,
      step: err.step || step,
      stepName: err.stepName || err.step_name || null,
      details: err.details || null,
    };
  }
  return {
    code: "UNKNOWN_ERROR",
    message: fallback,
    technicalMessage: String(err?.message || ""),
    step,
    stepName: null,
  };
}

function errorMessage(error) {
  if (!error) return "";
  if (typeof error === "string") return error;
  return error.message || ERROR_MESSAGES[error.code] || ERROR_TEXT;
}

function errorDiagnosticLine(error) {
  if (!error || typeof error !== "object") return "";
  return ERROR_HINTS[error.code] || "";
}

function errorDetailLine(error) {
  if (!error || typeof error !== "object") return "";
  const details = error.details || {};
  const tech = (error.technicalMessage || details.message || "").trim();
  if (tech && tech !== ERROR_MESSAGES[error.code] && tech !== error.message) {
    return tech;
  }
  return "";
}

const MOJIBAKE_PATTERN =
  /(Р РЋ|Р Рѓ|Р Сџ|Р Сњ|Р С›|Р С’|Р вЂ|РЎР|РЎв|РІР‚|Р’В|�)/g;

function looksLikeMojibake(value) {
  if (typeof value !== "string") return false;
  const matches = value.match(MOJIBAKE_PATTERN);
  return Boolean(matches && matches.length >= 2);
}

function isDisplayableSignal(signal) {
  const headline = signal?.headline || signal?.title || "";
  return Boolean(String(headline).trim()) && !looksLikeMojibake(headline);
}

function LockedAction({ onLogin }) {
  return (
    <button
      type="button"
      className="primary-button is-locked"
      onClick={onLogin}
      title="Доступно после входа"
      aria-label="Войдите, чтобы использовать"
    >
      <span className="lock-mark" aria-hidden="true">[locked]</span>
      <span>Войдите, чтобы использовать</span>
    </button>
  );
}

function EmptyState({ title, text, children, loading = false }) {
  return (
    <div className={loading ? "loading-state" : "empty-state"}>
      <div className="empty-state-title">{title}</div>
      <div className="empty-state-text">{text}</div>
      {children}
    </div>
  );
}

function SignalsSkeleton() {
  return (
    <div className="signals-skeleton" aria-label="Готовим карточки сигналов">
      {[0, 1, 2].map((i) => (
        <div className="signals-skeleton-row" key={i}>
          <span className="sk-block sk-hot" />
          <span className="sk-block sk-cat" />
          <span className="sk-block sk-title" />
          <span className="sk-block sk-meta" />
        </div>
      ))}
    </div>
  );
}

function MainSignalsState({ status, error }) {
  if (status === "loading") {
    return (
      <div className="signals-loading-state">
        <div className="signals-loading-hint">
          Сигналы появятся здесь после отбора. Прогресс анализа — выше.
        </div>
        <SignalsSkeleton />
      </div>
    );
  }

  if (status === "error") {
    return (
      <EmptyState
        title="Ошибка анализа"
        text={errorMessage(error) || ERROR_TEXT}
      />
    );
  }

  if (status === "empty") {
    return (
      <EmptyState
        title="Сигналы не найдены"
        text="Сильные сигналы не найдены. Возможно, всё ушло в шум или не прошло порог уверенности — посмотрите блок «Материалы, отброшенные как шум»."
      />
    );
  }

  return (
    <EmptyState
      title="Ожидание анализа"
      text="Добавьте ссылку, текст публикации или запустите демо-пример."
    />
  );
}

function currentRoute() {
  if (typeof window === "undefined") return "main";
  const path = window.location.pathname.replace(/\/+$/, "");
  if (path === "/about") return "about";
  if (path === "/profile") return "profile";
  if (path === "/digest") return "digest";
  return "main";
}

function DigestResultSummary({ metrics, onOpen }) {
  return (
    <section className="digest-result-summary" aria-labelledby="digest-result-title">
      <div>
        <div className="export-format-chip">result</div>
        <h3 id="digest-result-title">Дайджест собран</h3>
        <p>Итог анализа вынесен на отдельный экран, чтобы список сигналов оставался компактным.</p>
      </div>
      <div className="digest-result-metrics">
        <span><b>{metrics.signalCount}</b> выбранных сигналов</span>
        <span><b>{metrics.duplicatesCount}</b> дублей/перепечаток</span>
        <span><b>{metrics.noiseCount}</b> шум</span>
        <span><b>{metrics.noEvidenceCount}</b> без evidence</span>
      </div>
      <button type="button" className="primary-button digest-result-button" onClick={onOpen}>
        Открыть дайджест
      </button>
    </section>
  );
}

export default function App() {
  const [route, setRoute] = useState(currentRoute());
  const [currentUser, setCurrentUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [loginReason, setLoginReason] = useState("");
  const [loginTab, setLoginTab] = useState("login");
  const [pendingAction, setPendingAction] = useState(null);

  const [articles, setArticles] = useState([]);
  const [result, setResult] = useState(null);
  const topN = 5;
  const [loading, setLoading] = useState(false);
  const [loadingMode, setLoadingMode] = useState(null);
  const [error, setError] = useState("");
  const [pipelineStep, setPipelineStep] = useState(1);
  const [hasStartedAnalysis, setHasStartedAnalysis] = useState(false);
  const [selectedSignalIndex, setSelectedSignalIndex] = useState(0);
  const [inputMode, setInputMode] = useState("manual");
  const [manualText, setManualText] = useState("");
  const [firecrawlUrls, setFirecrawlUrls] = useState("");
  const [firecrawlItems, setFirecrawlItems] = useState([]);
  const [firecrawlArticles, setFirecrawlArticles] = useState([]);
  const [firecrawlErrors, setFirecrawlErrors] = useState([]);
  const [firecrawlStatus, setFirecrawlStatus] = useState("");

  const watchlistKey = watchlistStorageKey(currentUser);
  const [selectedWatchlistTopics, setSelectedWatchlistTopics] = useState(
    () => loadWatchlist(watchlistStorageKey(null)),
  );
  // Чтобы не слать trackEvent при первичной/автоматической загрузке из localStorage.
  const watchlistUserInitiated = useRef(false);

  useEffect(() => {
    // Смена пользователя (или гость ↔ user) — перечитать сохранённый список.
    setSelectedWatchlistTopics(loadWatchlist(watchlistKey));
    watchlistUserInitiated.current = false;
  }, [watchlistKey]);

  useEffect(() => {
    // Сохраняем выбор в текущий ключ. trackEvent — только если изменение
    // инициировано пользователем (не первичная гидратация из localStorage).
    saveWatchlist(watchlistKey, selectedWatchlistTopics);
    if (watchlistUserInitiated.current) {
      trackEvent({
        action: "update_watchlist",
        mode: "watchlist",
        feature: "watchlist",
        metadata: {
          topics: selectedWatchlistTopics,
          count: selectedWatchlistTopics.length,
        },
      });
      watchlistUserInitiated.current = false;
    }
  }, [watchlistKey, selectedWatchlistTopics]);

  function handleWatchlistChange(nextTopics) {
    watchlistUserInitiated.current = true;
    setSelectedWatchlistTopics(nextTopics);
  }

  useEffect(() => {
    if (route === "about") document.title = "BigPuzoTeam · О нас";
    else if (route === "profile") document.title = "TrendWatcher · Профиль";
    else if (route === "digest") document.title = "TrendWatcher · Итоговый дайджест";
    else document.title = PAGE_TITLE;
  }, [route]);

  useEffect(() => {
    function onPop() { setRoute(currentRoute()); }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  function navigateTo(path) {
    if (typeof window === "undefined") return;
    window.history.pushState(null, "", path);
    setRoute(currentRoute());
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  useEffect(() => {
    let mounted = true;
    fetchMe()
      .then((data) => {
        if (!mounted) return;
        setCurrentUser(data?.ok ? data.user : null);
      })
      .catch(() => { if (mounted) setCurrentUser(null); })
      .finally(() => { if (mounted) setAuthChecked(true); });
    if (route === "about") {
      trackEvent({ action: "visit_page", mode: "about", feature: "about_page" });
    } else if (route === "profile") {
      trackEvent({ action: "profile_opened", mode: "profile", feature: "profile_page" });
    } else if (route === "digest") {
      trackEvent({ action: "open_digest", mode: "digest", feature: "digest_page" });
    } else {
      trackEvent({ action: "visit_page", mode: "test_dataset", feature: "test_dataset" });
    }
    return () => { mounted = false; };
  }, [route]);

  const isGuest = authChecked && !currentUser;
  function openLoginForFeature(featureName) {
    requireLogin(
      featureName
        ? `Для функции «${featureName}» войдите или создайте аккаунт.`
        : "Для этой функции войдите или создайте аккаунт.",
      () => { /* пользователь сам нажмёт нужную кнопку после входа */ },
    );
  }

  const hasResult = Boolean(result);
  const rawSignals = Array.isArray(result?.signals) ? result.signals : [];
  const displayableSignals = rawSignals.filter(isDisplayableSignal);
  // Прикрепляем matchedTopics к каждому сигналу — общая лента, без отдельного блока.
  const signals = displayableSignals.map((s) => ({
    ...s,
    _matchedTopics: getMatchedTopics(s, selectedWatchlistTopics),
  }));
  const hasSignals = signals.length > 0;

  // Каждый новый набор сигналов — сбрасываем выбор на первый.
  useEffect(() => {
    if (!hasSignals) return;
    setSelectedSignalIndex((prev) =>
      prev >= 0 && prev < signals.length ? prev : 0,
    );
  }, [signals.length, result]);

  function handleSelectSignal(index) {
    setSelectedSignalIndex(index);
    if (typeof window !== "undefined") {
      requestAnimationFrame(() => {
        const el = document.getElementById("signal-detail");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }
  const resultsStatus = loading
    ? "loading"
    : error
      ? "error"
      : hasResult
        ? hasSignals ? "success" : "empty"
        : "idle";

  const rejectedRows = useMemo(() => {
    if (!result) return [];
    const byKey = new Map();
    [
      ...(result.rejected_items || []),
      ...(result.noise_items || []),
      ...(result.scored_articles || []).filter((a) => a.is_noise || a.decision === "reject"),
    ].forEach((a) => {
      const key = `${a?.url || ""}|${a?.title || a?.headline || ""}`;
      byKey.set(key, a);
    });
    return Array.from(byKey.values());
  }, [result]);

  const digestSummaryMetrics = useMemo(
    () => digestMetrics(result, signals, rejectedRows, selectedWatchlistTopics),
    [result, signals, rejectedRows, selectedWatchlistTopics],
  );

  function resetFirecrawlPreview() {
    setFirecrawlItems([]);
    setFirecrawlArticles([]);
    setFirecrawlErrors([]);
    setFirecrawlStatus("");
  }

  function requireLogin(reason, callback, tab = "login") {
    setLoginReason(reason || "Для этой функции нужно войти или создать аккаунт.");
    setLoginTab(tab);
    setPendingAction(() => callback);
    setLoginOpen(true);
    trackEvent({ action: "auth_required", mode: "custom", feature: "login" });
  }

  // Единая точка для защищённых действий. Если пользователь авторизован —
  // выполнить сразу; иначе сохранить pending action и открыть AuthModal.
  function requireAuthBeforeAction(action, featureName = "") {
    if (currentUser) {
      Promise.resolve().then(() => action());
      return;
    }
    const reason = featureName
      ? `Для функции «${featureName}» войдите или создайте аккаунт.`
      : "Для анализа своих источников войдите или создайте аккаунт.";
    requireLogin(reason, action);
  }

  function handleLoginSuccess(user) {
    setCurrentUser(user || null);
    setLoginOpen(false);
    const action = pendingAction;
    setPendingAction(null);
    if (typeof action === "function") {
      Promise.resolve().then(() => action());
    }
  }

  function handleLoginClose() {
    setLoginOpen(false);
    setPendingAction(null);
  }

  async function handleLogout() {
    try { await apiLogout(); } catch { /* ignore */ }
    setCurrentUser(null);
  }

  async function runAnalyze(nextArticles) {
    if (!nextArticles?.length) {
      setResult(null);
      setError("Нет материалов для анализа. Добавьте ссылку, текст публикации или запустите демо-пример.");
      return;
    }

    if (!currentUser) {
      requireLogin(
        "Для анализа своих источников войдите или создайте аккаунт.",
        () => runAnalyze(nextArticles),
      );
      return;
    }

    setHasStartedAnalysis(true);
    setLoading(true);
    setLoadingMode("analyze");
    setPipelineStep(2);
    setError("");
    setResult(null);
    scrollTo("pipeline");

    try {
      const analysis = await analyzeArticles({ articles: nextArticles, topN });
      setArticles(nextArticles);
      setResult(analysis);
      setPipelineStep(6);
      setTimeout(() => scrollTo("signals"), 50);
    } catch (err) {
      if (err instanceof AuthRequiredError) {
        setCurrentUser(null);
        requireLogin(
          "Сессия истекла. Войдите снова, чтобы продолжить анализ.",
          () => runAnalyze(nextArticles),
        );
      } else {
        setError(normalizeError(err, ERROR_TEXT, err?.step || 4));
        setPipelineStep(err?.step || 4);
      }
    } finally {
      setLoading(false);
      setLoadingMode(null);
    }
  }

  async function handleUseSample() {
    setHasStartedAnalysis(true);
    setLoading(true);
    setLoadingMode("analyze");
    setError("");
    setResult(null);
    resetFirecrawlPreview();
    scrollTo("pipeline");

    try {
      const analysis = await analyzeSample();
      setArticles(analysis?.scored_articles || []);
      setResult(analysis);
      setPipelineStep(6);
      setTimeout(() => scrollTo("signals"), 50);
    } catch (err) {
      setResult(null);
      setError(normalizeError(err, ERROR_TEXT, err?.step || 4));
      setPipelineStep(err?.step || 4);
    } finally {
      setLoading(false);
      setLoadingMode(null);
    }
  }

  function handleCsv(file) {
    if (!file) return;
    setError("");

    if (!currentUser) {
      requireLogin(
        "Загрузка своего CSV доступна после входа или регистрации. Для демо используйте «Запустить пример».",
        () => handleCsv(file),
      );
      return;
    }

    window.Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true,
      complete: (parseResult) => {
        if (parseResult.errors.length) {
          setError("CSV не распознан. Проверьте заголовки: id, title, source, url, date, snippet.");
          return;
        }
        resetFirecrawlPreview();
        runAnalyze(parseResult.data);
      },
      error: () => setError("Не удалось прочитать CSV-файл."),
    });
  }

  function handleManualTextAnalyze() {
    const blocks = manualText
      .split(/\n\s*\n/g)
      .map((block) => block.trim())
      .filter(Boolean);

    if (!blocks.length) {
      setError("Вставьте текст публикации или загрузите CSV.");
      return;
    }

    const nextArticles = blocks.map((block, index) => {
      const firstLine = block.split("\n").find(Boolean) || `Текст ${index + 1}`;
      return {
        id: `manual-${index + 1}`,
        title: firstLine.slice(0, 120),
        source: "Ручной ввод",
        url: `manual://source-${index + 1}`,
        date: "",
        snippet: block,
      };
    });

    if (!currentUser) {
      requireLogin(
        "Для анализа своего текста войдите или создайте аккаунт.",
        () => runAnalyze(nextArticles),
      );
      return;
    }

    resetFirecrawlPreview();
    runAnalyze(nextArticles);
  }

  async function handleSearch(query, limit) {
    if (!currentUser) {
      requireLogin(
        "Поиск Firecrawl доступен после входа или регистрации.",
        () => handleSearch(query, limit),
      );
      return;
    }

    setHasStartedAnalysis(true);
    setLoading(true);
    setLoadingMode("search");
    setPipelineStep(1);
    setError("");
    setResult(null);
    scrollTo("pipeline");

    try {
      const data = await searchFirecrawl(query, limit);
      if (data?.ok === false) {
        setError(normalizeError({
          code: data.error || "NO_URLS_FOUND",
          message: data.message,
          requestId: data.request_id,
          step: data.step || 1,
          stepName: data.step_name || "firecrawl_search",
        }, ERROR_MESSAGES.NO_URLS_FOUND, data.step || 1));
        setPipelineStep(data.step || 1);
        setLoading(false);
        setLoadingMode(null);
        return;
      }
      const arts = data.articles || [];
      if (arts.length > 0) {
        setPipelineStep(2);
        await runAnalyze(arts);
      } else {
        setError("Firecrawl не нашёл публикации по запросу. Измените формулировку или запустите демо-пример.");
        setLoading(false);
        setLoadingMode(null);
      }
    } catch (err) {
      if (err instanceof AuthRequiredError) {
        setCurrentUser(null);
        requireLogin("Сессия истекла. Войдите снова.", () => handleSearch(query, limit));
      } else {
        setError(normalizeError(err, ERROR_TEXT, err?.step || 1));
        setPipelineStep(err?.step || 1);
      }
      setLoading(false);
      setLoadingMode(null);
    }
  }

  async function handleCrawl(sourceUrls, limit) {
    const invalidUrls = (sourceUrls || []).filter((u) => !/^https?:\/\/.+\..+/.test(u));
    if (invalidUrls.length) {
      setError(
        `Неверный формат ссылок: ${invalidUrls.slice(0, 2).join(", ")}${invalidUrls.length > 2 ? ` и ещё ${invalidUrls.length - 2}` : ""}. Ссылки должны начинаться с https://`
      );
      return;
    }

    if (!currentUser) {
      requireLogin(
        "Обход через Firecrawl доступен после входа или регистрации.",
        () => handleCrawl(sourceUrls, limit),
      );
      return;
    }

    setHasStartedAnalysis(true);
    setLoading(true);
    setLoadingMode("crawl");
    setPipelineStep(1);
    setError("");
    setResult(null);
    resetFirecrawlPreview();
    scrollTo("pipeline");

    try {
      const data = await crawlFirecrawlSources(sourceUrls, limit);
      const arts = data.articles || [];
      if (arts.length > 0) {
        setPipelineStep(2);
        await runAnalyze(arts);
      } else {
        setError("Публикации не найдены. Проверьте URL или измените глубину обхода.");
        setLoading(false);
        setLoadingMode(null);
      }
    } catch (err) {
      if (err instanceof AuthRequiredError) {
        setCurrentUser(null);
        requireLogin("Сессия истекла. Войдите снова.", () => handleCrawl(sourceUrls, limit));
      } else {
        setError(normalizeError(err, ERROR_TEXT, err?.step || 1));
        setPipelineStep(err?.step || 1);
      }
      setLoading(false);
      setLoadingMode(null);
    }
  }

  async function handleFirecrawlLoad() {
    const urls = firecrawlUrls
      .split(/\r?\n/g)
      .map((url) => url.trim())
      .filter(Boolean);

    if (!urls.length) {
      setError("Вставьте хотя бы одну ссылку.");
      return;
    }

    const invalidUrls = urls.filter((u) => !/^https?:\/\/.+\..+/.test(u));
    if (invalidUrls.length) {
      setError(
        `Неверный формат ссылок: ${invalidUrls.slice(0, 2).join(", ")}${invalidUrls.length > 2 ? ` и ещё ${invalidUrls.length - 2}` : ""}. Ссылки должны начинаться с https://`
      );
      return;
    }

    if (!currentUser) {
      requireLogin(
        "Загрузка своих URL доступна после входа или регистрации.",
        () => handleFirecrawlLoad(),
      );
      return;
    }

    setLoading(true);
    setLoadingMode("firecrawl");
    setPipelineStep(1);
    setError("");
    setResult(null);
    setFirecrawlStatus("");
    setFirecrawlItems([]);
    setFirecrawlArticles([]);
    setFirecrawlErrors([]);

    try {
      const data = await scrapeFirecrawlUrls(urls);
      const nextArticles = data.articles || [];
      setFirecrawlItems(data.items || []);
      setFirecrawlArticles(nextArticles);
      setFirecrawlErrors(data.errors || []);
      setArticles(nextArticles);
      setFirecrawlStatus(data.ok ? "success" : "partial");

      if (!data.ok && !nextArticles.length) {
        setError("Не удалось загрузить публикации. Проверьте ссылки или запустите демо-пример.");
      }
    } catch (err) {
      if (err instanceof AuthRequiredError) {
        setCurrentUser(null);
        requireLogin("Сессия истекла. Войдите снова.", () => handleFirecrawlLoad());
      } else {
        setError(normalizeError(err, ERROR_TEXT, err?.step || 1));
        setPipelineStep(err?.step || 1);
        setFirecrawlStatus("error");
      }
    } finally {
      setLoading(false);
      setLoadingMode(null);
    }
  }

  const authBadge = !authChecked ? null : currentUser ? (
    <span className="auth-badge-wrap">
      <a
        href="/profile"
        className="auth-user-button"
        title="Открыть профиль"
        aria-current={route === "profile" ? "page" : undefined}
      >
        <span className="auth-user-avatar">
          {(currentUser.username || "?").slice(0, 1).toUpperCase()}
        </span>
        <span className="auth-user-name">
          {currentUser.username}
          {currentUser.role === "admin" && <span className="auth-user-role">admin</span>}
        </span>
      </a>
    </span>
  ) : (
    <span className="auth-badge auth-badge-off">
      <button
        className="auth-badge-link auth-badge-primary"
        type="button"
        onClick={() => { setLoginReason(""); setLoginTab("login"); setLoginOpen(true); }}
      >
        Войти
      </button>
      <button
        className="auth-badge-link"
        type="button"
        onClick={() => { setLoginReason(""); setLoginTab("register"); setLoginOpen(true); }}
      >
        Регистрация
      </button>
    </span>
  );

  if (route === "about") {
    return (
      <>
        <AboutPage authBadge={authBadge} />
        <LoginModal
          open={loginOpen}
          reason={loginReason}
          initialTab={loginTab}
          onClose={handleLoginClose}
          onSuccess={handleLoginSuccess}
        />
      </>
    );
  }

  if (route === "profile") {
    return (
      <>
        <ProfilePage
          currentUser={currentUser}
          authChecked={authChecked}
          authBadge={authBadge}
          onLogout={async () => {
            await handleLogout();
            if (typeof window !== "undefined") window.location.href = "/";
          }}
          onRequireLogin={(reason) =>
            requireLogin(
              reason || "Войдите, чтобы открыть профиль.",
              () => { if (typeof window !== "undefined") window.location.href = "/profile"; },
            )
          }
        />
        <LoginModal
          open={loginOpen}
          reason={loginReason}
          initialTab={loginTab}
          onClose={handleLoginClose}
          onSuccess={handleLoginSuccess}
        />
      </>
    );
  }

  if (route === "digest") {
    return (
      <DigestPage
        authBadge={authBadge}
        result={result}
        signals={signals}
        rejectedRows={rejectedRows}
        status={resultsStatus}
        currentUser={currentUser}
        selectedWatchlistTopics={selectedWatchlistTopics}
        onTrackEvent={trackEvent}
        onBack={() => navigateTo("/")}
      />
    );
  }

  return (
    <div className="app-shell">
      <Header authBadge={authBadge} />

      <div className="layout">
        <section className="app-section" style={{ paddingTop: 20, paddingBottom: 20 }}>
          <div className="sec-head">
            <div className="num">01 · Вход</div>
            <div>
              <h2>Что анализируем?</h2>
              <p>
                TrendWatcher помогает быстро разобрать публикации, показать важные сигналы,
                объяснить оценку важности и собрать дайджест для команды.
              </p>
            </div>
          </div>

          <div className="input-selector">
            <button
              type="button"
              className={`input-option ${inputMode === "manual" ? "is-active" : ""}`}
              onClick={() => setInputMode("manual")}
            >
              <div className="io-num">01</div>
              <div className="io-body">
                <div className="io-title">Текст или CSV</div>
                <div className="io-desc">Вставьте текст публикации или загрузите CSV-файл</div>
              </div>
            </button>

            <button
              type="button"
              className={`input-option ${inputMode === "firecrawl" ? "is-active" : ""} ${isGuest ? "is-locked" : ""}`}
              onClick={() => setInputMode("firecrawl")}
            >
              <div className="io-num">02</div>
              <div className="io-body">
                <div className="io-title">
                  По ссылкам
                  {isGuest && <span className="io-locked-pill">требует входа</span>}
                </div>
                <div className="io-desc">Загрузите публикации по списку URL</div>
              </div>
            </button>

            <button
              type="button"
              className={`input-option ${inputMode === "crawl" ? "is-active" : ""} ${isGuest ? "is-locked" : ""}`}
              onClick={() => setInputMode("crawl")}
            >
              <div className="io-num">03</div>
              <div className="io-body">
                <div className="io-title">
                  Поиск Firecrawl
                  {isGuest && <span className="io-locked-pill">требует входа</span>}
                </div>
                <div className="io-desc">Найдите публикации по запросу или источнику</div>
              </div>
            </button>

            <button
              type="button"
              className="input-option input-option-run"
              disabled={loading}
              onClick={handleUseSample}
            >
              <div className="io-num io-run">▶</div>
              <div className="io-body">
                <div className="io-title">Запустить пример</div>
                <div className="io-desc">Демо на подготовленном наборе материалов</div>
              </div>
            </button>
          </div>

          <div className="settings-row" style={{ paddingTop: 14, paddingBottom: 4 }}>
            <p className="period-note">
              Период анализа: последние 12 месяцев. Материалы старше года не попадают в дайджест.
            </p>
          </div>

          <WatchlistPanel
            selectedTopics={selectedWatchlistTopics}
            onChange={handleWatchlistChange}
            currentUser={currentUser}
          />

          {inputMode === "manual" && (
            <div className="input-panel">
              {isGuest ? (
                <div className="secondary-button is-locked" aria-disabled="true">
                  <span className="lock-mark" aria-hidden="true">[locked]</span>
                  Загрузить CSV — после входа
                </div>
              ) : (
                <label className="secondary-button">
                  Загрузить CSV
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    disabled={loading}
                    onChange={(event) => handleCsv(event.target.files?.[0])}
                  />
                </label>
              )}
              <textarea
                className="source-textarea"
                value={manualText}
                onChange={(event) => setManualText(event.target.value)}
                placeholder="Вставьте текст одной или нескольких публикаций. Разделяйте материалы пустой строкой."
                rows={7}
              />
              {isGuest ? (
                <LockedAction
                  label="Сформировать дайджест"
                  hint="Авторизуйтесь, чтобы анализировать свой текст"
                  onLogin={() => openLoginForFeature("Свой текст / CSV")}
                />
              ) : (
                <button className="primary-button" disabled={loading} onClick={handleManualTextAnalyze}>
                  Сформировать дайджест
                </button>
              )}
            </div>
          )}

          {inputMode === "firecrawl" && (
            <div className="input-panel">
              <textarea
                className="source-textarea"
                value={firecrawlUrls}
                onChange={(event) => setFirecrawlUrls(event.target.value)}
                placeholder="https://example.com/article-1&#10;https://example.com/article-2"
                rows={6}
              />
              {isGuest ? (
                <LockedAction
                  label="Загрузить публикации"
                  hint="Авторизуйтесь, чтобы загружать свои URL через Firecrawl"
                  onLogin={() => openLoginForFeature("Firecrawl: по ссылкам")}
                />
              ) : (
                <div className="firecrawl-actions">
                  <button className="primary-button" disabled={loading} onClick={handleFirecrawlLoad}>
                    Загрузить публикации
                  </button>
                  <button
                    className="secondary-button"
                    disabled={loading || firecrawlArticles.length === 0}
                    onClick={() => runAnalyze(firecrawlArticles)}
                  >
                    Сформировать дайджест
                  </button>
                </div>
              )}

              {firecrawlStatus === "success" && (
                <div className="success-box">Источники загружены. Можно формировать дайджест.</div>
              )}

              {firecrawlStatus === "partial" && firecrawlErrors.length > 0 && (
                <div className="warning-box">
                  Часть источников не загрузилась. Остальные материалы можно отправить на анализ.
                </div>
              )}

              {firecrawlItems.length > 0 && (
                <div className="preview-list">
                  <div className="section-heading">
                    <p>Предпросмотр</p>
                    <span>{firecrawlItems.length} источников</span>
                  </div>
                  {firecrawlItems.map((item) => (
                    <article className="preview-item" key={item.url}>
                      <h3>
                        {item.title || item.url}
                        {item.potentialDuplicate && <span>Возможный дубль</span>}
                      </h3>
                      <a href={item.url} target="_blank" rel="noreferrer">{item.url}</a>
                      <p>{(item.text || item.markdown || "").slice(0, 500)}</p>
                    </article>
                  ))}
                </div>
              )}
            </div>
          )}

          {inputMode === "crawl" && (
            <div className="input-panel">
              <FirecrawlPanel
                loading={loading}
                onSearch={handleSearch}
                onCrawl={handleCrawl}
                isGuest={isGuest}
                onLogin={() => openLoginForFeature("Firecrawl: поиск и обход")}
              />
            </div>
          )}

          {hasStartedAnalysis && (
            <div style={{ marginTop: 20 }}>
              <PipelineSteps
                active={hasResult ? 6 : pipelineStep}
                errorStep={!loading && error ? (error.step || pipelineStep) : null}
              />
            </div>
          )}

          {error && (
            <div className="error-box">
              <div className="error-box-message">{errorMessage(error)}</div>
              {typeof error === "object" && (
                <div className="error-box-diagnostic">{errorDiagnosticLine(error)}</div>
              )}
              {typeof error === "object" && errorDetailLine(error) && (
                <div className="error-box-detail">{errorDetailLine(error)}</div>
              )}
              {DEV_MODE && typeof error === "object" && (
                <details className="technical-details">
                  <summary>Технические детали</summary>
                  <pre>{JSON.stringify({
                    code: error.code,
                    request_id: error.requestId,
                    step: error.step,
                    step_name: error.stepName,
                    message: error.technicalMessage,
                    details: error.details,
                  }, null, 2)}</pre>
                </details>
              )}
            </div>
          )}
          {loading && <SearchProgress mode={loadingMode} activeStep={pipelineStep} />}

          {result && <div style={{ marginTop: 28 }}><StatsBar stats={result.stats} /></div>}
        </section>

        {hasStartedAnalysis && (
        <section className="app-section" id="signals">
          <div className="sec-head">
            <div className="num">02 · Сигналы</div>
            <div>
              <h2>Сигналы из публикаций</h2>
              <p>
                Карточка показывает краткую выжимку, почему сигнал важен сейчас,
                источники, факторы важности и черновик для команды.
              </p>
            </div>
          </div>

          <div className="content-grid results-layout">
            <div className="main-column signals-panel">
              {resultsStatus === "success" ? (
                <SourceTable
                  articles={signals}
                  title="Главные сигналы"
                  countText={`${signals.length} сигналов`}
                  selectedIndex={selectedSignalIndex}
                  onSelect={handleSelectSignal}
                />
              ) : (
                <div className="table-section">
                  <div className="section-heading">
                    <p>Главные сигналы</p>
                    <span>
                      {resultsStatus === "idle" && "Анализ не запущен"}
                      {resultsStatus === "loading" && "Анализируем"}
                      {resultsStatus === "error" && "Ошибка"}
                      {resultsStatus === "empty" && "0 сигналов"}
                    </span>
                  </div>
                  <MainSignalsState status={resultsStatus} error={error} />
                </div>
              )}

              {hasResult && !loading && (
                <DigestResultSummary
                  metrics={digestSummaryMetrics}
                  onOpen={() => navigateTo("/digest")}
                />
              )}

            </div>
          </div>

          {resultsStatus === "success" && signals[selectedSignalIndex] && (
            <div className="signals-section" id="signal-detail">
              <div className="section-heading" style={{ marginTop: 32 }}>
                <p>Детали сигнала</p>
                <span>
                  выбран #{String(selectedSignalIndex + 1).padStart(2, "0")} из {signals.length}
                </span>
              </div>
              <div className="signal-list">
                <SignalCard
                  key={`detail-${selectedSignalIndex}`}
                  signal={signals[selectedSignalIndex]}
                  index={selectedSignalIndex}
                  defaultOpen
                  static
                />
              </div>
            </div>
          )}
        </section>
        )}
      </div>

      <footer className="team-section">
        <div className="team-inner">
          <div className="team-grid">
            <div>
              <div className="team-mark">Команда BigPuzoTeam</div>
              <p className="team-statement">
                TrendWatcher для продуктовой команды банка
              </p>
            </div>
            <div className="team-block">
              <span className="lbl">Проект</span>
              <b>TrendWatcher</b><br />
              <span className="team-block-sub">команда BigPuzoTeam</span>
            </div>
            <div className="team-block">
              <span className="lbl">Фокус</span>
              <b>Финтех-сигналы</b><br />
              продуктовый анализ<br />
              дайджест для команды
            </div>
          </div>
          <div className="team-creators">
            <span className="lbl">Создатели</span>
            <div className="creators-list">
              <span className="creator-slot">Лычман Александр · Backend, DevOps</span>
              <span className="creator-slot">Лыткин Владислав · ML</span>
              <span className="creator-slot">Мальцев Егор · Product manager</span>
            </div>
            <a href="/about" className="creators-more">Больше о нас</a>
          </div>
        </div>
      </footer>

      <LoginModal
        open={loginOpen}
        reason={loginReason}
        onClose={handleLoginClose}
        onSuccess={handleLoginSuccess}
      />
    </div>
  );
}
