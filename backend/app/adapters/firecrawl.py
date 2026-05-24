import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "yclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "ref",
    "ref_src",
    "spm",
}
TRACKING_PREFIXES = ("utm_",)


class FirecrawlConfigError(Exception):
    pass


class FirecrawlUrlError(Exception):
    pass


class FirecrawlFetchError(Exception):
    """Generic Firecrawl failure. Carries the original status code when available."""

    def __init__(self, message: str, *, status: int | None = None,
                 response_body: str | None = None):
        super().__init__(message)
        self.status = status
        self.response_body = response_body


class FirecrawlAuthError(FirecrawlFetchError):
    """Firecrawl returned 401/403 — API key invalid or revoked."""


class FirecrawlRateLimitError(FirecrawlFetchError):
    """Firecrawl returned 429 — quota/rate limit."""


class FirecrawlEmptyContentError(Exception):
    pass


def _extract_status(exc: BaseException) -> int | None:
    """Best-effort extraction of an HTTP status code from any Firecrawl SDK error."""
    for attr in ("status_code", "status", "http_status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        for attr in ("status_code", "status"):
            value = getattr(response, attr, None)
            if isinstance(value, int):
                return value
    # Some SDKs put the status in the message: "... 401 Unauthorized ..."
    import re as _re
    match = _re.search(r"\b(4\d\d|5\d\d)\b", str(exc))
    if match:
        return int(match.group(1))
    return None


def _extract_response_body(exc: BaseException) -> str | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    text = getattr(response, "text", None) or getattr(response, "content", None)
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8", errors="replace")
        except Exception:
            text = None
    if isinstance(text, str):
        return text[:600]
    return None


_AUTH_KEYWORDS = (
    "unauthorized", "invalid api key", "invalid_api_key", "api key",
    "forbidden", "permission denied", "not authorized", "authentication",
)
_RATE_LIMIT_KEYWORDS = (
    "rate limit", "rate-limit", "too many requests", "quota exceeded",
    "concurrent limit",
)


def _wrap_sdk_error(exc: BaseException, default_message: str) -> FirecrawlFetchError:
    """Map any SDK exception onto the right FirecrawlFetchError subclass."""
    status = _extract_status(exc)
    body = _extract_response_body(exc)
    base_message = f"{type(exc).__name__}: {exc}".strip(": ")
    message = base_message or default_message
    haystack = f"{message}\n{body or ''}".lower()

    is_auth = status in (401, 403) or any(k in haystack for k in _AUTH_KEYWORDS)
    is_rate = status == 429 or any(k in haystack for k in _RATE_LIMIT_KEYWORDS)
    if is_auth and not is_rate:
        return FirecrawlAuthError(message, status=status or 401, response_body=body)
    if is_rate:
        return FirecrawlRateLimitError(message, status=status or 429, response_body=body)
    return FirecrawlFetchError(message, status=status, response_body=body)


def validate_url(url: str) -> str:
    candidate = (url or "").strip()
    try:
        parsed = urlsplit(candidate)
    except ValueError as exc:
        raise FirecrawlUrlError("Некорректный URL") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise FirecrawlUrlError("Некорректный URL")

    return candidate


def normalize_url(url: str) -> str:
    valid_url = validate_url(url)
    parsed = urlsplit(valid_url)
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    query = urlencode(query_pairs, doseq=True)
    path = parsed.path.rstrip("/") or ""
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            query,
            "",
        )
    )


def deduplicate_urls(urls: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for url in urls:
        normalized = normalize_url(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def scrape_url(url: str) -> dict:
    normalized_url = normalize_url(url)
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise FirecrawlConfigError("Firecrawl API key не настроен")

    try:
        raw_result = _scrape_with_sdk(api_key, normalized_url)
    except FirecrawlFetchError:
        raise
    except Exception as exc:
        raise _wrap_sdk_error(exc, "Не удалось получить страницу") from exc

    result = _unwrap_result(raw_result)
    markdown = _pick_string(result, "markdown", "content")
    html = _pick_string(result, "html", "rawHtml", "raw_html")
    text = _markdown_to_text(markdown) or _html_to_text(html)

    if not markdown and text:
        markdown = text

    if not markdown.strip() and not text.strip():
        raise FirecrawlEmptyContentError("Firecrawl вернул пустой контент")

    metadata = _pick_metadata(result)
    title = _pick_string(metadata, "title", "og_title", "ogTitle", "og:title")

    return {
        "url": normalized_url,
        "title": title,
        "markdown": markdown.strip(),
        "text": text.strip(),
        "sourceType": "firecrawl",
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
    }


def search_firecrawl(query: str, limit: int = 10, lang: str = "ru") -> dict:
    if not query.strip():
        raise FirecrawlUrlError("Поисковый запрос не может быть пустым")
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise FirecrawlConfigError("Firecrawl API key не настроен")

    pages = _search_with_sdk(api_key, query.strip(), limit, lang)
    items = []
    for page in pages:
        result = _unwrap_result(page)
        markdown = _pick_string(result, "markdown", "content", "snippet", "description")
        html = _pick_string(result, "html", "rawHtml", "raw_html")
        text = _markdown_to_text(markdown) or _html_to_text(html)
        if not markdown and text:
            markdown = text
        metadata = _pick_metadata(result)
        title = (
            _pick_string(result, "title")
            or _pick_string(metadata, "title", "og_title", "ogTitle", "og:title")
        )
        page_url = (
            _pick_string(result, "url", "source_url", "sourceUrl", "link", "href")
            or _pick_string(metadata, "url", "source_url", "sourceURL", "og_url", "ogUrl")
            or ""
        )
        # Firecrawl v2 search may return only a title + url + description WITHOUT a
        # body when scrape_options is not provided. Keep those rows so the caller
        # can decide whether to enrich them later — but skip ones without any url.
        if not page_url and not (markdown.strip() or text.strip() or title.strip()):
            continue
        items.append({
            "url": page_url,
            "title": title,
            "markdown": markdown.strip(),
            "text": text.strip(),
            "sourceType": "firecrawl_search",
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
        })

    hints = _duplicate_hints(items)
    for item in items:
        item["potentialDuplicate"] = hints.get(item.get("url", ""), False)

    return {"items": items, "errors": []}


def normalize_firecrawl_results(raw) -> list[dict]:
    """Adapter for any plausible Firecrawl-shaped response.

    Accepts dicts with `data` / `results` / `links` / `urls` / `documents`,
    plain lists of strings, or lists of objects with `url|link|sourceUrl|title`.
    Always returns: [{url, title|None, source|None, snippet|None}, ...].
    """
    if raw is None:
        return []
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    if hasattr(raw, "dict") and not isinstance(raw, dict):
        try:
            raw = raw.dict()
        except Exception:
            pass

    candidates: list = []
    if isinstance(raw, dict):
        # Top-level v2 buckets — concatenate all that exist.
        for key in ("web", "news", "images"):
            value = raw.get(key)
            if isinstance(value, list):
                candidates.extend(value)
        if not candidates:
            for key in ("data", "results", "links", "urls", "documents", "items"):
                value = raw.get(key)
                if isinstance(value, list):
                    candidates = value
                    break
                if isinstance(value, dict):
                    inner_collected = []
                    for inner_key in ("web", "news", "results", "data", "items"):
                        inner = value.get(inner_key)
                        if isinstance(inner, list):
                            inner_collected.extend(inner)
                    if inner_collected:
                        candidates = inner_collected
                        break
    elif isinstance(raw, list):
        candidates = raw

    normalized: list[dict] = []
    for entry in candidates:
        if entry is None:
            continue
        if isinstance(entry, str):
            url = entry.strip()
            if url:
                normalized.append({"url": url, "title": None, "source": None, "snippet": None})
            continue
        if hasattr(entry, "model_dump"):
            entry = entry.model_dump()
        elif hasattr(entry, "dict"):
            try:
                entry = entry.dict()
            except Exception:
                pass
        if not isinstance(entry, dict):
            continue
        url = (
            entry.get("url")
            or entry.get("link")
            or entry.get("sourceUrl")
            or entry.get("source_url")
            or entry.get("href")
            or ""
        )
        title = entry.get("title") or entry.get("name") or None
        source = entry.get("source") or entry.get("publisher") or None
        snippet = (
            entry.get("description")
            or entry.get("snippet")
            or entry.get("summary")
            or entry.get("markdown")
            or None
        )
        if not url and not title:
            continue
        normalized.append({
            "url": str(url or "").strip(),
            "title": str(title).strip() if title else None,
            "source": str(source).strip() if source else None,
            "snippet": str(snippet).strip() if snippet else None,
        })
    return normalized


def crawl_url(url: str, limit: int = 15) -> dict:
    normalized_url = normalize_url(url)
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise FirecrawlConfigError("Firecrawl API key не настроен")

    pages = _crawl_with_sdk(api_key, normalized_url, limit)
    items = []
    for page in pages:
        result = _unwrap_result(page)
        markdown = _pick_string(result, "markdown", "content")
        html = _pick_string(result, "html", "rawHtml", "raw_html")
        text = _markdown_to_text(markdown) or _html_to_text(html)
        if not markdown and text:
            markdown = text
        if not markdown.strip() and not text.strip():
            continue
        metadata = _pick_metadata(result)
        title = _pick_string(metadata, "title", "og_title", "ogTitle", "og:title")
        page_url = (
            _pick_string(result, "url", "source_url", "sourceUrl")
            or _pick_string(metadata, "url", "source_url", "sourceURL", "og_url", "ogUrl")
            or normalized_url
        )
        items.append({
            "url": page_url,
            "title": title,
            "markdown": markdown.strip(),
            "text": text.strip(),
            "sourceType": "firecrawl_crawl",
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
        })
    return {"items": items, "errors": []}


def crawl_urls(urls: list[str], limit: int = 15) -> dict:
    all_items = []
    errors = []
    seen: set[str] = set()

    for url in urls:
        try:
            normalized = normalize_url(url)
        except FirecrawlUrlError as exc:
            errors.append({"url": url, "message": str(exc)})
            continue
        try:
            result = crawl_url(normalized, limit)
            for item in result["items"]:
                item_url = item.get("url", "")
                if item_url not in seen:
                    seen.add(item_url)
                    all_items.append(item)
        except (FirecrawlConfigError, FirecrawlUrlError, FirecrawlFetchError) as exc:
            errors.append({"url": normalized, "message": str(exc)})
        except Exception:
            errors.append({"url": normalized, "message": "Не удалось обойти источник (см. логи)"})

    hints = _duplicate_hints(all_items)
    for item in all_items:
        item["potentialDuplicate"] = hints.get(item.get("url", ""), False)

    return {"items": all_items, "errors": errors}


def scrape_urls(urls: list[str]) -> dict:
    items = []
    errors = []
    normalized_urls = []
    seen = set()

    for url in urls:
        try:
            normalized = normalize_url(url)
        except FirecrawlUrlError as exc:
            errors.append({"url": url, "message": str(exc)})
            continue

        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_urls.append(normalized)

    for normalized_url in normalized_urls:
        try:
            items.append(scrape_url(normalized_url))
        except (FirecrawlConfigError, FirecrawlUrlError, FirecrawlFetchError, FirecrawlEmptyContentError) as exc:
            errors.append({"url": normalized_url, "message": str(exc)})
        except Exception:
            errors.append({"url": normalized_url, "message": "Не удалось получить страницу"})

    hints = _duplicate_hints(items)
    for item in items:
        item["potentialDuplicate"] = hints.get(item.get("url", ""), False)

    return {"items": items, "errors": errors}


def firecrawl_items_to_articles(items: list[dict]) -> list[dict]:
    articles = []
    duplicate_hints = _duplicate_hints(items)
    for index, item in enumerate(items, start=1):
        markdown = item.get("markdown") or ""
        text = item.get("text") or _markdown_to_text(markdown) or ""
        title = item.get("title") or _title_from_text(text) or item.get("url", "")
        full_text = _compact_text(text)
        snippet = full_text[:700]
        if item.get("potentialDuplicate") or duplicate_hints.get(item.get("url", "")):
            snippet = f"[Potential duplicate] {snippet}"

        articles.append(
            {
                "id": f"firecrawl-{index}",
                "title": title,
                "source": _source_from_url(item.get("url", "")) or item.get("source") or "Firecrawl",
                "url": item.get("url", ""),
                "date": item.get("publishedAt") or item.get("date") or item.get("fetchedAt", ""),
                "snippet": snippet,
                "full_text": full_text,
                "markdown": markdown.strip(),
                "fetched_at": item.get("fetchedAt", ""),
            }
        )
    return articles


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered in TRACKING_PARAMS or any(lowered.startswith(prefix) for prefix in TRACKING_PREFIXES)


def _flatten_search_data(result) -> list:
    """Firecrawl v2 search returns SearchData with web/news/images buckets."""
    plain = _to_plain_data(result)
    buckets = []
    if isinstance(plain, dict):
        for key in ("web", "news", "images"):
            value = plain.get(key)
            if isinstance(value, list):
                buckets.extend(value)
        if not buckets:
            for key in ("data", "results", "documents"):
                value = plain.get(key)
                if isinstance(value, list):
                    buckets.extend(value)
                elif isinstance(value, dict):
                    for inner_key in ("web", "news", "results", "data"):
                        inner = value.get(inner_key)
                        if isinstance(inner, list):
                            buckets.extend(inner)
    elif isinstance(plain, list):
        buckets = plain
    return [_to_plain_data(item) for item in buckets]


def _search_with_sdk(api_key: str, query: str, limit: int, lang: str) -> list:
    """Talk to the live Firecrawl SDK. Errors propagate as FirecrawlFetchError subclasses.

    We try a richer call first (with scrape_options so search results include
    markdown content) and progressively strip kwargs on TypeError. `lang` is
    accepted on input for backward compatibility but no longer forwarded — the
    Firecrawl v4 SDK doesn't have a `lang` kwarg, and mapping it to `location`
    rejects some values silently. Pure text-search behavior is what we want here.
    """
    try:
        from firecrawl import Firecrawl
    except ImportError as exc:
        raise FirecrawlFetchError("Firecrawl SDK не установлен") from exc

    try:
        from firecrawl.v2.types import ScrapeOptions  # type: ignore
        scrape_options = ScrapeOptions(formats=["markdown"])
    except Exception:
        scrape_options = None

    client = Firecrawl(api_key=api_key)
    base_kwargs = {"limit": max(1, min(30, int(limit or 10)))}
    if scrape_options is not None:
        base_kwargs["scrape_options"] = scrape_options

    last_exc: BaseException | None = None
    # Try the richest call → progressively strip kwargs that any SDK build might reject.
    for kwargs in (base_kwargs, {"limit": base_kwargs["limit"]}):
        try:
            result = client.search(query, **kwargs)
            return _flatten_search_data(result)
        except TypeError as exc:
            last_exc = exc
            continue
        except Exception as exc:
            raise _wrap_sdk_error(exc, "Не удалось выполнить поиск") from exc

    # All attempts hit TypeError — SDK signature mismatch.
    raise _wrap_sdk_error(
        last_exc or RuntimeError("Firecrawl SDK rejected every supported call shape"),
        "Не удалось выполнить поиск (SDK signature)",
    ) from last_exc


def _crawl_with_sdk(api_key: str, url: str, limit: int) -> list:
    try:
        from firecrawl import Firecrawl
    except ImportError as exc:
        raise FirecrawlFetchError("Firecrawl SDK не установлен") from exc

    try:
        from firecrawl.v2.types import ScrapeOptions  # type: ignore
        scrape_options = ScrapeOptions(formats=["markdown"])
    except Exception:
        scrape_options = None

    client = Firecrawl(api_key=api_key)
    kwargs = {"limit": int(limit or 15), "poll_interval": 2, "timeout": 120}
    if scrape_options is not None:
        kwargs["scrape_options"] = scrape_options
    try:
        job = client.crawl(url, **kwargs)
    except TypeError:
        try:
            job = client.crawl(url, limit=kwargs["limit"])
        except Exception as exc:
            raise _wrap_sdk_error(exc, "Не удалось обойти источник") from exc
    except Exception as exc:
        raise _wrap_sdk_error(exc, "Не удалось обойти источник") from exc

    pages = getattr(job, "data", None)
    if pages is None and isinstance(job, dict):
        pages = job.get("data", [])
    if pages is None:
        pages = job if isinstance(job, list) else []
    return [_to_plain_data(p) for p in pages]


def _scrape_with_sdk(api_key: str, url: str):
    try:
        from firecrawl import Firecrawl
    except ImportError as exc:
        raise FirecrawlFetchError("Firecrawl SDK не установлен") from exc

    client = Firecrawl(api_key=api_key)
    try:
        return client.scrape(url, formats=["markdown"])
    except TypeError:
        try:
            return client.scrape(url)
        except Exception as exc:
            raise _wrap_sdk_error(exc, "Не удалось получить страницу") from exc
    except Exception as exc:
        raise _wrap_sdk_error(exc, "Не удалось получить страницу") from exc


def _unwrap_result(result):
    data = _to_plain_data(result)
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    return data if isinstance(data, dict) else {}


def _to_plain_data(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return {
            key: _to_plain_data(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


def _pick_string(mapping, *keys):
    if not isinstance(mapping, dict):
        return ""
    for key in keys:
        value = mapping.get(key)
        if value:
            return str(value)
    return ""


def _pick_metadata(result):
    metadata = result.get("metadata") if isinstance(result, dict) else {}
    return metadata if isinstance(metadata, dict) else {}


def _markdown_to_text(markdown: str) -> str:
    if not markdown:
        return ""
    text = re.sub(r"```.*?```", " ", markdown, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)]\([^)]*\)", r"\1", text)
    text = re.sub(r"[#>*_`~|-]+", " ", text)
    return _compact_text(text)


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return _compact_text(unescape(text))


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _title_from_text(text: str) -> str:
    compact = _compact_text(text)
    if not compact:
        return ""
    return compact[:90]


def _source_from_url(url: str) -> str:
    try:
        host = urlsplit(url).netloc
    except ValueError:
        return ""
    return host.removeprefix("www.")


def _duplicate_hints(items: list[dict]) -> dict[str, bool]:
    hints = {}
    titles = {}
    url_keys = []
    for item in items:
        title_key = _compact_text(item.get("title", "")).lower()
        url = item.get("url", "")
        parsed = urlsplit(url)
        url_key = f"{parsed.netloc}{parsed.path}".lower().rstrip("/")

        if title_key:
            hints[url] = hints.get(url, False) or title_key in titles
            titles[title_key] = url
        if url_key:
            similar_url = any(
                existing_host == parsed.netloc.lower()
                and SequenceMatcher(None, existing_path, parsed.path.lower().rstrip("/")).ratio() >= 0.9
                for existing_host, existing_path in url_keys
            )
            hints[url] = hints.get(url, False) or similar_url
            url_keys.append((parsed.netloc.lower(), parsed.path.lower().rstrip("/")))
    return hints
