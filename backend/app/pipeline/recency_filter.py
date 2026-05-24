"""Filter articles by publication recency.

Articles older than `MAX_AGE_DAYS` and articles without a verifiable
publication date should not become final signals — they go to the rejected
bucket with a Russian reason ready for the UI.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Iterable

MAX_AGE_DAYS = 365

OLDER_THAN_YEAR_REASON = (
    "Материал старше 12 месяцев и не подходит для актуального финтех-дайджеста."
)
MISSING_DATE_REASON = (
    "Не удалось подтвердить дату публикации."
)


def _try_iso(value: str) -> datetime | None:
    candidates = [value]
    if " " in value:
        candidates.append(value.replace(" ", "T", 1))
    candidates.append(value.replace("Z", "+00:00"))
    candidates.append(value[:10])
    for cand in candidates:
        try:
            dt = datetime.fromisoformat(cand)
        except (ValueError, TypeError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _parse_date(value) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    dt = _try_iso(raw)
    if dt is not None:
        return dt

    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is not None:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    return None


_DATE_KEYS = (
    "published_at",
    "publishedAt",
    "pubDate",
    "date",
    "articleDate",
    "createdAt",
    "created_at",
    "fetched_at",
    "fetchedAt",
)


def article_date(article: dict) -> datetime | None:
    for key in _DATE_KEYS:
        dt = _parse_date(article.get(key))
        if dt is not None:
            return dt
    meta = article.get("metadata")
    if isinstance(meta, dict):
        dt = _parse_date(
            meta.get("date")
            or meta.get("published_at")
            or meta.get("pubDate")
            or meta.get("publishedAt")
        )
        if dt is not None:
            return dt
    return None


def filter_by_recency(
    articles: Iterable[dict],
    *,
    max_age_days: int = MAX_AGE_DAYS,
    now: datetime | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (fresh, too_old, no_date).

    `too_old` and `no_date` items are dicts annotated with `reject_reason`
    and `rejection_reason` in Russian so they can be passed straight to
    `normalize_rejected_item`.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)

    fresh: list[dict] = []
    too_old: list[dict] = []
    no_date: list[dict] = []

    for article in articles:
        dt = article_date(article)
        if dt is None:
            no_date.append({
                **article,
                "decision": "reject",
                "reject_reason": MISSING_DATE_REASON,
                "rejection_reason": MISSING_DATE_REASON,
                "category": "Шум / нерелевантное",
            })
            continue
        if dt < cutoff:
            too_old.append({
                **article,
                "decision": "reject",
                "reject_reason": OLDER_THAN_YEAR_REASON,
                "rejection_reason": OLDER_THAN_YEAR_REASON,
                "category": "Шум / нерелевантное",
            })
            continue
        fresh.append(article)

    return fresh, too_old, no_date
