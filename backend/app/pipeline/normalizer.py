from __future__ import annotations

import hashlib
import math
from urllib.parse import urlsplit

from .quality_scorer import SCORING_VERSION


DEFAULT_IMPORTANCE_BREAKDOWN = {
    "bank_relevance": 0,
    "signal_type_weight": 0,
    "novelty": 0,
    "source_quality": 0,
    "recency": 0,
    "evidence_strength": 0,
    "user_or_market_impact": 0,
}

DEFAULT_CONFIDENCE_BREAKDOWN = {
    "has_valid_title": False,
    "has_publication_date": False,
    "extraction_quality": 0,
    "source_reliability": 0,
    "has_primary_source": False,
    "cross_source_confirmation": 0,
    "entity_extraction_quality": 0,
    "llm_json_validity": 0,
    "fintech_anchor_density": 0,
    "concrete_event_signal": 0,
    "relevance_certainty": 0,
    "duplicate_or_repost_penalty": 0,
    "weak_content_penalty": 0,
}


def normalize_result(result: dict | None) -> dict:
    normalized = dict(result or {})
    signals = [normalize_signal_card(card, idx) for idx, card in enumerate(normalized.get("signals") or [])]
    scored = [normalize_scored_item(item, idx) for idx, item in enumerate(normalized.get("scored_articles") or [])]
    rejected = [normalize_scored_item(item, idx) for idx, item in enumerate(normalized.get("rejected_items") or [])]
    normalized["signals"] = signals
    normalized["scored_articles"] = scored
    normalized["rejected_items"] = rejected
    normalized.setdefault("duplicates", [])
    normalized.setdefault("digest", "")
    normalized.setdefault("stats", {})
    normalized["ok"] = True
    normalized["response_schema"] = "analysis_result.v2"
    return normalized


def normalize_signal_card(card: dict | None, index: int = 0) -> dict:
    item = dict(card or {})
    title = _text(item.get("headline") or item.get("title"), f"Signal {index + 1}")
    url = _text(item.get("url"))
    importance = _number(item.get("importance", item.get("hotness")), 0, 0, 100)
    confidence = _number(item.get("confidence"), 0.35, 0, 1)
    sources = item.get("sources") if isinstance(item.get("sources"), list) else []
    if not sources:
        sources = [_source_from_item(item)]

    normalized = {
        **item,
        "id": _text(item.get("id") or item.get("article_id")) or _stable_id(url or title or str(index)),
        "headline": title,
        "title": _text(item.get("title") or title, title),
        "url": url,
        "source": _text(item.get("source") or _source_from_url(url), "Unknown"),
        "published_at": _nullable_text(item.get("published_at") or item.get("date") or item.get("fetched_at")),
        "category": _text(item.get("category"), "Market"),
        "summary": _text(item.get("summary") or item.get("summary_fact"), title),
        "why_now": _text(item.get("why_now") or item.get("whyNow") or item.get("bank_relevance"), ""),
        "whyNow": _text(item.get("whyNow") or item.get("why_now") or item.get("bank_relevance"), ""),
        "importance": importance,
        "hotness": importance,
        "confidence": confidence,
        "importance_breakdown": _dict(item.get("importance_breakdown"), DEFAULT_IMPORTANCE_BREAKDOWN),
        "confidence_breakdown": _dict(item.get("confidence_breakdown"), DEFAULT_CONFIDENCE_BREAKDOWN),
        "importance_reason": _text(item.get("importance_reason"), "Rule-based scoring fallback."),
        "confidence_reason": _text(item.get("confidence_reason"), "Rule-based confidence fallback."),
        "sources": sources,
        "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
        "is_duplicate": bool(item.get("is_duplicate", False)),
        "duplicate_cluster_id": _nullable_text(item.get("duplicate_cluster_id")),
        "primary_source_url": _nullable_text(item.get("primary_source_url") or url),
        "scoring_version": _text(item.get("scoring_version"), SCORING_VERSION),
    }
    normalized["why_now"] = normalized["why_now"] or normalized["summary"]
    normalized["whyNow"] = normalized["whyNow"] or normalized["why_now"]
    return normalized


def normalize_scored_item(item: dict | None, index: int = 0) -> dict:
    normalized = normalize_signal_card(item, index)
    normalized["decision"] = _text((item or {}).get("decision"), "keep")
    normalized["is_noise"] = bool((item or {}).get("is_noise", False))
    normalized["reject_reason"] = _text((item or {}).get("reject_reason") or (item or {}).get("rejection_reason"), "")
    normalized["rejection_reason"] = normalized["reject_reason"]
    return normalized


def _dict(value, defaults):
    data = dict(defaults)
    if isinstance(value, dict):
        data.update(value)
    return data


def _number(value, fallback, lower, upper):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    if not math.isfinite(number):
        number = fallback
    return max(lower, min(upper, round(number, 2)))


def _text(value, fallback=""):
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.lower() in {"undefined", "null", "nan"}:
        return fallback
    return text


def _nullable_text(value):
    text = _text(value, "")
    return text or None


def _stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _source_from_item(item: dict) -> dict:
    return {
        "url": _text(item.get("url")),
        "title": _text(item.get("title") or item.get("headline")),
        "source": _text(item.get("source") or _source_from_url(item.get("url", "")), "Unknown"),
        "kind": _text(item.get("source_type"), "unknown"),
    }


def _source_from_url(url: str) -> str:
    try:
        return urlsplit(str(url or "")).netloc.removeprefix("www.")
    except ValueError:
        return ""
