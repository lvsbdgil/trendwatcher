"""Firecrawl proxy endpoints: scrape, search, crawl."""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request

from .. import analytics
from ..adapters.firecrawl import (
    FirecrawlAuthError,
    FirecrawlConfigError,
    FirecrawlFetchError,
    FirecrawlRateLimitError,
    crawl_urls,
    firecrawl_items_to_articles,
    normalize_firecrawl_results,
    scrape_urls,
    search_firecrawl,
)
from ..deps import require_auth
from ..pipeline.logging import AnalysisLogger, console_error, new_request_id
from ..schemas import FirecrawlCrawlRequest, FirecrawlScrapeRequest, FirecrawlSearchRequest
from ._errors import http_error


router = APIRouter(tags=["firecrawl"])
logger = logging.getLogger(__name__)
_DEBUG = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")


def _request_id(request: Request) -> str:
    rid = getattr(getattr(request, "state", None), "request_id", None)
    return rid or new_request_id()


def _user_id(user: dict | None) -> int | None:
    return user.get("id") if isinstance(user, dict) else None


def _firecrawl_details(exc: BaseException) -> dict:
    sdk_cause = exc.__cause__ or exc
    return {
        "sdk_error": type(sdk_cause).__name__,
        "status": getattr(exc, "status", None),
        "response_body": (getattr(exc, "response_body", None) or "")[:240] or None,
        "message": str(exc)[:300],
    }


@router.post("/api/firecrawl/scrape")
def firecrawl_scrape(
    payload: FirecrawlScrapeRequest, request: Request, user: dict = Depends(require_auth)
):
    request_id = _request_id(request)
    log = AnalysisLogger(request_id=request_id, limit=len(payload.urls), user_id=_user_id(user))
    urls = [u for u in payload.urls if str(u).strip()]
    if not urls:
        http_error(400, "NO_URLS_FOUND", "Field 'urls' must not be empty",
                   request_id=request_id, step=1)
    if not os.environ.get("FIRECRAWL_API_KEY", "").strip():
        http_error(503, "FIRECRAWL_API_KEY_MISSING", "Firecrawl API key is not configured.",
                   request_id=request_id, step=1)

    log.step_started(1, "firecrawl_scrape", url_count=len(urls))
    result = scrape_urls(urls)
    articles = firecrawl_items_to_articles(result["items"])
    errors = result["errors"]
    ok = len(errors) == 0
    log.step_completed(1, "firecrawl_scrape", found_urls=len(result["items"]),
                       extracted_documents=len(articles), errors=len(errors))

    if not result["items"] and errors:
        http_error(502, "EXTRACTION_FAILED", "Could not extract content from the supplied pages.",
                   request_id=request_id, step=1, details={"errors": errors[:5]})

    analytics.log_event(
        request, action="use_firecrawl", mode="custom",
        feature="firecrawl", status="success" if ok else "fail", user=user,
        metadata={"urls": len(urls), "items": len(result["items"]), "errors": len(errors)},
    )
    return {
        "ok": ok,
        "items": result["items"],
        "articles": articles,
        "errors": errors,
        "request_id": request_id,
        "message": "" if ok else "Часть источников не загрузилась",
    }


@router.post("/api/firecrawl/search")
def firecrawl_search(
    payload: FirecrawlSearchRequest, request: Request, user: dict = Depends(require_auth)
):
    request_id = _request_id(request)
    log = AnalysisLogger(request_id=request_id, query=payload.query,
                         limit=payload.limit, user_id=_user_id(user))
    if not payload.query.strip():
        http_error(400, "NO_URLS_FOUND", "Field 'query' must not be empty",
                   request_id=request_id, step=1, step_name="firecrawl_search")

    has_key = bool(os.environ.get("FIRECRAWL_API_KEY", "").strip())
    print(
        f"[analysis:{request_id}] firecrawl_search started "
        f"query=\"{payload.query[:80]}\" limit={payload.limit} hasFirecrawlKey={has_key}",
        flush=True,
    )

    try:
        log.step_started(1, "firecrawl_search", selected_limit=payload.limit,
                         query_len=len(payload.query))
        result = search_firecrawl(payload.query, payload.limit, payload.lang)
    except FirecrawlConfigError:
        http_error(503, "FIRECRAWL_API_KEY_MISSING",
                   "Firecrawl API key не настроен на сервере",
                   request_id=request_id, step=1, step_name="firecrawl_search")
    except FirecrawlAuthError as exc:
        details = _firecrawl_details(exc)
        log.error("FIRECRAWL_AUTH_FAILED", exc, step=1, step_name="firecrawl_search", **details)
        http_error(502, "FIRECRAWL_AUTH_FAILED",
                   f"Firecrawl отклонил API ключ ({exc.status}): {exc}",
                   request_id=request_id, step=1, step_name="firecrawl_search", details=details)
    except FirecrawlRateLimitError as exc:
        details = _firecrawl_details(exc)
        log.error("FIRECRAWL_RATE_LIMIT", exc, step=1, step_name="firecrawl_search", **details)
        http_error(429, "FIRECRAWL_RATE_LIMIT",
                   "Firecrawl временно ограничил запросы (429)",
                   request_id=request_id, step=1, step_name="firecrawl_search", details=details)
    except FirecrawlFetchError as exc:
        details = _firecrawl_details(exc)
        log.error("FIRECRAWL_REQUEST_FAILED", exc, step=1, step_name="firecrawl_search", **details)
        http_error(502, "FIRECRAWL_REQUEST_FAILED", f"{type(exc).__name__}: {exc}",
                   request_id=request_id, step=1, step_name="firecrawl_search", details=details)
    except Exception as exc:
        analytics.log_event(
            request, action="error_event", mode="custom",
            feature="firecrawl", status="fail", user=user,
            metadata={"error": f"{type(exc).__name__}: {str(exc)[:200]}", "request_id": request_id},
        )
        log.error("UNKNOWN_ERROR", exc, step=1, step_name="firecrawl_search")
        logger.exception("Firecrawl search failed: %s", exc)
        http_error(500, "UNKNOWN_ERROR", f"{type(exc).__name__}: {exc}",
                   request_id=request_id, step=1, step_name="firecrawl_search")

    articles = firecrawl_items_to_articles(result["items"])
    errors = result["errors"]
    print(
        f"[analysis:{request_id}] firecrawl_search response "
        f"status=200 resultType={type(result).__name__} urlsCount={len(result['items'])}",
        flush=True,
    )
    log.step_completed(1, "firecrawl_search", count=len(result["items"]),
                       extracted_documents=len(articles), errors=len(errors))

    analytics.log_event(
        request, action="use_firecrawl", mode="custom",
        feature="firecrawl", status="success" if not errors else "fail", user=user,
        metadata={"query_len": len(payload.query), "items": len(result["items"]),
                  "errors": len(errors)},
    )

    if not result["items"]:
        return {
            "ok": False,
            "error": "NO_URLS_FOUND",
            "message": "По запросу ничего не найдено, попробуйте более конкретный финтех-запрос",
            "items": [],
            "articles": [],
            "errors": errors,
            "request_id": request_id,
            "step": 1,
            "step_name": "firecrawl_search",
        }

    return {
        "ok": len(errors) == 0,
        "items": result["items"],
        "articles": articles,
        "errors": errors,
        "request_id": request_id,
        "message": "" if not errors else "Часть запросов не выполнена",
    }


@router.post("/api/firecrawl/crawl")
def firecrawl_crawl(
    payload: FirecrawlCrawlRequest, request: Request, user: dict = Depends(require_auth)
):
    request_id = _request_id(request)
    log = AnalysisLogger(request_id=request_id, limit=payload.limit, user_id=_user_id(user))
    urls = [u for u in payload.urls if str(u).strip()]
    if not urls:
        http_error(400, "NO_URLS_FOUND", "Field 'urls' must not be empty",
                   request_id=request_id, step=1)
    if not os.environ.get("FIRECRAWL_API_KEY", "").strip():
        http_error(503, "FIRECRAWL_API_KEY_MISSING", "Firecrawl API key is not configured.",
                   request_id=request_id, step=1)

    log.step_started(1, "firecrawl_crawl", url_count=len(urls), selected_limit=payload.limit)
    result = crawl_urls(urls, payload.limit)
    articles = firecrawl_items_to_articles(result["items"])
    errors = result["errors"]
    ok = len(errors) == 0
    log.step_completed(1, "firecrawl_crawl", found_urls=len(result["items"]),
                       extracted_documents=len(articles), errors=len(errors))

    if not result["items"] and errors:
        http_error(502, "EXTRACTION_FAILED", "Could not extract content from the supplied pages.",
                   request_id=request_id, step=1, details={"errors": errors[:5]})

    analytics.log_event(
        request, action="use_external_fetch", mode="custom",
        feature="firecrawl", status="success" if ok else "fail", user=user,
        metadata={"urls": len(urls), "limit": payload.limit,
                  "items": len(result["items"]), "errors": len(errors)},
    )
    return {
        "ok": ok,
        "items": result["items"],
        "articles": articles,
        "errors": errors,
        "request_id": request_id,
        "message": "" if ok else "Часть источников не удалось обойти",
    }


@router.get("/api/debug/firecrawl")
def firecrawl_self_test(
    request: Request, query: str = "fintech", user: dict = Depends(require_auth)
):
    request_id = _request_id(request)
    if not _DEBUG and user.get("role") != "admin":
        http_error(403, "ADMIN_REQUIRED", "Доступ только для администраторов.",
                   request_id=request_id, step=1, step_name="firecrawl_search")

    has_key = bool(os.environ.get("FIRECRAWL_API_KEY", "").strip())
    if not has_key:
        return {
            "ok": False, "request_id": request_id,
            "errorCode": "FIRECRAWL_API_KEY_MISSING",
            "errorMessage": "Firecrawl API key не настроен на сервере",
            "failedStep": "firecrawl_search",
            "hasFirecrawlKey": False,
        }

    print(
        f"[analysis:{request_id}] firecrawl_self_test started "
        f"query=\"{query[:80]}\" limit=3 hasFirecrawlKey=True",
        flush=True,
    )
    try:
        raw = search_firecrawl(query, limit=3, lang="ru")
    except FirecrawlAuthError as exc:
        return {
            "ok": False, "request_id": request_id,
            "errorCode": "FIRECRAWL_AUTH_FAILED", "failedStep": "firecrawl_search",
            "errorMessage": f"Firecrawl отклонил API ключ ({exc.status}): {exc}",
            "hasFirecrawlKey": True,
        }
    except FirecrawlRateLimitError:
        return {
            "ok": False, "request_id": request_id,
            "errorCode": "FIRECRAWL_RATE_LIMIT", "failedStep": "firecrawl_search",
            "errorMessage": "Firecrawl временно ограничил запросы (429)",
            "hasFirecrawlKey": True,
        }
    except FirecrawlFetchError as exc:
        return {
            "ok": False, "request_id": request_id,
            "errorCode": "FIRECRAWL_REQUEST_FAILED", "failedStep": "firecrawl_search",
            "errorMessage": f"{type(exc).__name__}: {exc}",
            "status": getattr(exc, "status", None),
            "hasFirecrawlKey": True,
        }
    except Exception as exc:
        console_error(request_id, "firecrawl_search", exc, route="/api/debug/firecrawl")
        return {
            "ok": False, "request_id": request_id,
            "errorCode": "UNKNOWN_ERROR", "failedStep": "firecrawl_search",
            "errorMessage": f"{type(exc).__name__}: {exc}",
            "hasFirecrawlKey": True,
        }

    items = raw.get("items", [])
    return {
        "ok": True,
        "request_id": request_id,
        "hasFirecrawlKey": True,
        "status": 200,
        "urlsCount": len(items),
        "firstUrls": [item.get("url") for item in items[:3]],
        "normalized": normalize_firecrawl_results(items)[:3],
    }
