// Default to "" so that in dev the requests hit the Vite dev server which
// proxies /api → backend (same-origin → httpOnly cookies just work). In prod
// the FastAPI app serves the SPA, so same-origin too.
// To talk to an external backend, set VITE_API_URL at build time.
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

async function hashPassword(plain) {
  const data = new TextEncoder().encode(plain);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export class AuthRequiredError extends Error {
  constructor(message = "Войдите или создайте аккаунт.") {
    super(message);
    this.name = "AuthRequiredError";
    this.status = 401;
    this.code = "AUTH_REQUIRED";
  }
}

export class ApiError extends Error {
  constructor(message, { status, code, requestId, step, stepName, details } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code || "API_ERROR";
    this.requestId = requestId || null;
    this.step = step || null;
    this.stepName = stepName || null;
    this.details = details || null;
  }
}

function parseDetail(data) {
  // backend errors come as { detail: { ok:false, error:CODE, message:"..." } }
  // or { detail: "string" } for stock FastAPI errors
  const detail = data?.detail;
  if (detail && typeof detail === "object") {
    return {
      code: detail.error || "API_ERROR",
      message: detail.message || "",
      requestId: detail.request_id || null,
      step: detail.step || null,
      stepName: detail.step_name || null,
      details: detail.details || null,
    };
  }
  if (typeof detail === "string") {
    return { code: "API_ERROR", message: detail };
  }
  return { code: "API_ERROR", message: "" };
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch (networkErr) {
    throw new ApiError("Не удалось подключиться к серверу", {
      status: 0,
      code: "NETWORK_ERROR",
    });
  }

  const data = await response.json().catch(() => null);
  const headerRequestId = response.headers?.get?.("x-request-id") || null;

  if (response.status === 401) {
    const { code, message, requestId, step, stepName, details } = parseDetail(data);
    if (code === "AUTH_REQUIRED") {
      throw new AuthRequiredError(message || undefined);
    }
    throw new ApiError(message || "Неверный логин или пароль.",
                       { status: 401, code, requestId: requestId || headerRequestId,
                         step, stepName, details });
  }

  if (!response.ok) {
    const { code, message, requestId, step, stepName, details } = parseDetail(data);
    throw new ApiError(message || `Ошибка сервера (${response.status})`,
                       { status: response.status, code,
                         requestId: requestId || headerRequestId,
                         step, stepName, details });
  }

  return data;
}

export async function getSampleArticles() {
  return request("/api/sample");
}

export async function analyzeSample() {
  return request("/api/sample/analyze", { method: "POST" });
}

export async function analyzeArticles({ articles, topN }) {
  return request("/api/analyze", {
    method: "POST",
    body: JSON.stringify({
      articles,
      top_n: Number(topN),
    }),
  });
}

export async function scrapeFirecrawlUrls(urls) {
  return request("/api/firecrawl/scrape", {
    method: "POST",
    body: JSON.stringify({ urls }),
  });
}

export async function crawlFirecrawlSources(urls, limit = 15) {
  return request("/api/firecrawl/crawl", {
    method: "POST",
    body: JSON.stringify({ urls, limit }),
  });
}

export async function searchFirecrawl(query, limit = 10, lang = "ru") {
  return request("/api/firecrawl/search", {
    method: "POST",
    body: JSON.stringify({ query, limit, lang }),
  });
}

export async function fetchMe() {
  return request("/api/auth/me");
}

export async function login(username, password) {
  return request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password: await hashPassword(password) }),
  });
}

export async function register(username, password) {
  return request("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password: await hashPassword(password) }),
  });
}

export async function logout() {
  return request("/api/auth/logout", { method: "POST" });
}

export async function fetchProfile() {
  return request("/api/user/profile");
}

export async function fetchUserEvents(limit = 50, offset = 0) {
  return request(`/api/user/events?limit=${limit}&offset=${offset}`);
}

export async function changePassword(oldPassword, newPassword) {
  const [oldHash, newHash] = await Promise.all([hashPassword(oldPassword), hashPassword(newPassword)]);
  return request("/api/user/change-password", {
    method: "POST",
    body: JSON.stringify({ oldPassword: oldHash, newPassword: newHash }),
  });
}

export async function trackEvent({ action, mode, feature, metadata }) {
  try {
    await request("/api/track", {
      method: "POST",
      body: JSON.stringify({ action, mode, feature, metadata }),
    });
  } catch {
    /* analytics best-effort */
  }
}

export async function adminFetchSummary() {
  return request("/api/admin/metrics/summary");
}

export async function adminFetchEvents(params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  });
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request(`/api/admin/metrics/events${suffix}`);
}

export async function adminFetchUsers() {
  return request("/api/admin/users");
}

export async function adminFetchUsageByDay(days = 14) {
  return request(`/api/admin/metrics/usage-by-day?days=${days}`);
}
