"""Scoring v2: importance and confidence with breakdown and reasons.

Goals:
- importance (0-100) is a deterministic, explainable score from 7 factors;
- confidence (0.05-0.98) reflects how much we can trust the signal card,
  not how "sure" the LLM was. Reject items fall to 0.20-0.45 organically,
  not via a hard cap;
- both return breakdown + human reason — so the UI can explain results.

No randomness. Differences come from features of the article (text length,
date, source type, anchor density, evidence count, cross-source confirmation,
etc.), not from buckets that collapse different articles to the same number.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .source_quality import TRUSTED_MEDIA_DOMAINS


SCORING_VERSION = "v2"


# ─── Russian humanizers for technical enum values ──────────────────────────

EVENT_TYPE_RU = {
    "regulation": "регулирование",
    "launch": "запуск продукта",
    "ux_change": "UX-изменение",
    "partnership": "партнёрство",
    "market_signal": "рыночный сигнал",
    "other": "прочее",
}

SOURCE_TYPE_RU = {
    "primary": "первоисточник",
    "trusted_media": "авторитетное СМИ",
    "reprint": "пересказ",
    "unknown": "неизвестно",
}

PRODUCT_AREA_RU = {
    "payments": "платежи",
    "banking": "банкинг",
    "embedded_finance": "embedded finance",
    "identity": "идентификация",
    "investments": "инвестиции",
    "insurance": "страхование",
    "ux": "UX",
}


def _ru_event(value):
    return EVENT_TYPE_RU.get(value, value or "—")


def _ru_source(value):
    return SOURCE_TYPE_RU.get(value, value or "—")


def _ru_area(value):
    return PRODUCT_AREA_RU.get(value, value or "—")


# ─── Factor maxes (sum = 100) ──────────────────────────────────────────────

IMPORTANCE_MAX = {
    "bank_relevance": 25,
    "signal_type_weight": 20,
    "novelty": 15,
    "source_quality": 15,
    "recency": 10,
    "evidence_strength": 10,
    "user_or_market_impact": 5,
}


FINTECH_TERMS_FOR_RELEVANCE = (
    "bank", "payment", "card", "wallet", "loan", "credit", "mortgage",
    "deposit", "checkout", "merchant", "fintech", "finance", "transfer",
    "remittance", "regulator", "regulation", "compliance", "kyc",
    "open banking", "embedded finance", "baas", "bnpl", "cbdc",
    "neobank", "lending",
    "банк", "платеж", "платёж", "карт", "кошел",
    "кредит", "ипотек", "вклад", "депозит", "займ", "заём", "заем",
    "счет", "счёт", "перевод", "сбп",
    "эквайринг", "эмисси",
    "финансов", "финтех",
    "регулятор", "цб ", "банк россии", "минфин", "фнс",
    "страхов", "инвестиц", "брокер", "биржа",
    "рассрочк", "кэшбэк", "кешбэк",
    "криптовалют", "стейблкоин", "цифровой рубль",
)


# ─── Importance ────────────────────────────────────────────────────────────

def _gather_text(signal: dict) -> str:
    keys = ("title", "headline", "summary_fact", "bank_relevance", "snippet", "full_text")
    return " ".join(str(signal.get(k, "") or "") for k in keys)


def _count_fintech_anchors(text_l: str) -> int:
    return sum(1 for term in FINTECH_TERMS_FOR_RELEVANCE if term in text_l)


def compute_bank_relevance(signal: dict) -> tuple[float, str]:
    """0–25. How tightly the material ties to bank products / regulation / UX."""
    category = signal.get("category", "")
    product_area = signal.get("product_area", "")
    text_l = _gather_text(signal).lower()

    by_category = {
        "Регулирование": 21.0,
        "Платёжный сервис": 18.0,
        "Банковский продукт": 17.0,
        "UX-механика": 14.0,
        "Партнёрство": 13.0,
        "Рынок": 8.0,
        "Шум / нерелевантное": 3.0,
        "PR / кадровое": 5.0,
    }
    base = by_category.get(category, 7.0)

    if product_area in {"payments", "banking", "embedded_finance"}:
        base += 2.5
    elif product_area in {"identity", "investments", "insurance"}:
        base += 1.5
    elif product_area == "ux":
        base += 1.0

    anchor_hits = _count_fintech_anchors(text_l)
    base += min(5.0, anchor_hits * 0.45)

    score = max(0.0, min(IMPORTANCE_MAX["bank_relevance"], base))
    parts = [f"категория: {category or '—'}"]
    if product_area:
        parts.append(f"продуктовая область: {_ru_area(product_area)}")
    parts.append(f"финтех-якорей: {anchor_hits}")
    return score, ", ".join(parts)


def compute_signal_type_weight(signal: dict) -> tuple[float, str]:
    """0–20. launch/regulation/partnership > market/other."""
    event_type = signal.get("event_type", "other")
    base = {
        "regulation": 19.0,
        "launch": 16.0,
        "ux_change": 14.0,
        "partnership": 13.0,
        "market_signal": 7.0,
        "other": 2.0,
    }.get(event_type, 2.0)

    if signal.get("user_scenario"):
        base += 1.5
    actors = signal.get("actors") or []
    if len(actors) >= 2:
        base += 1.0
    if signal.get("decision") == "reject":
        base = min(base, 8.0)

    score = max(0.0, min(IMPORTANCE_MAX["signal_type_weight"], base))
    parts = [f"тип события: {_ru_event(event_type)}"]
    if actors:
        parts.append(f"участников: {len(actors)}")
    else:
        parts.append("участники не выделены")
    return score, ", ".join(parts)


def compute_novelty(signal: dict) -> tuple[float, str]:
    """0–15. Primary launch is novel; reprint/market summary is not."""
    source_type = signal.get("source_type", "unknown")
    event_type = signal.get("event_type", "other")

    base = 10.0
    if source_type == "primary":
        base += 2.5
    elif source_type == "reprint":
        base -= 5.0
    elif source_type == "trusted_media":
        base += 0.5

    if event_type == "launch":
        base += 2.0
    elif event_type == "regulation":
        base += 1.5
    elif event_type == "market_signal":
        base -= 2.0
    elif event_type == "other":
        base -= 4.0

    # cross-source confirmation slightly reduces "fresh-fact" novelty value
    # (everyone reporting the same story → not novel any more)
    cross = max(1, int(signal.get("cross_source_count") or 1))
    if cross >= 4:
        base -= 1.0

    score = max(0.0, min(IMPORTANCE_MAX["novelty"], base))
    return score, (
        f"источник: {_ru_source(source_type)}, "
        f"тип события: {_ru_event(event_type)}, "
        f"подтверждений: {cross}"
    )


def compute_source_quality(signal: dict) -> tuple[float, str]:
    """0–15 from source_score (0–100) + primary bonus + trusted host bonus."""
    source_score = float(signal.get("source_score") or 50)
    base = source_score / 100.0 * 12.5

    if signal.get("is_primary_source"):
        base += 2.0

    url = (signal.get("url") or "").lower()
    if any(domain in url for domain in TRUSTED_MEDIA_DOMAINS):
        base += 0.5

    score = max(0.0, min(IMPORTANCE_MAX["source_quality"], base))
    primary_tag = "есть первоисточник" if signal.get("is_primary_source") else "первоисточник не подтверждён"
    return score, f"оценка источника: {int(source_score)}/100, {primary_tag}"


def _parse_age_days(value: str) -> int | None:
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    candidates = [raw, raw[:10]]
    for cand in candidates:
        try:
            dt = datetime.fromisoformat(cand)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).days)
        except (ValueError, TypeError):
            continue
    return None


def compute_recency(signal: dict) -> tuple[float, str]:
    """0–10. Continuous decay so two articles 4 and 11 days old differ."""
    published = signal.get("published_at") or signal.get("date") or ""
    age_days = _parse_age_days(published)
    if age_days is None:
        return 4.0, "дата не указана"

    if age_days <= 1:
        score = 10.0
    elif age_days <= 7:
        # 10 → 8 over days 1..7
        score = 10.0 - (age_days - 1) * (2.0 / 6.0)
    elif age_days <= 30:
        # 8 → 6
        score = 8.0 - (age_days - 7) * (2.0 / 23.0)
    elif age_days <= 90:
        # 6 → 4
        score = 6.0 - (age_days - 30) * (2.0 / 60.0)
    elif age_days <= 180:
        # 4 → 2
        score = 4.0 - (age_days - 90) * (2.0 / 90.0)
    else:
        score = max(0.5, 2.0 - (age_days - 180) / 240.0)

    score = max(0.0, min(IMPORTANCE_MAX["recency"], score))
    return score, f"возраст ~{age_days} дн."


def _evidence_text_length(evidence: Iterable) -> int:
    total = 0
    for item in evidence or []:
        if isinstance(item, dict):
            total += len(str(item.get("quote") or ""))
        elif isinstance(item, str):
            total += len(item)
    return total


_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_PRODUCT_RE = re.compile(r"\b(launch|launched|introduces?|rolls out|регулирован|запуст|представ|выпуст|обнов)\b",
                          re.IGNORECASE)


def compute_evidence_strength(signal: dict) -> tuple[float, str]:
    """0–10. Count + length + numbers/dates + cross-source confirmations."""
    evidence = signal.get("evidence") or []
    cross = max(1, int(signal.get("cross_source_count") or len(signal.get("sources") or []) or 1))

    score = 0.0
    score += min(5.0, len(evidence) * 2.2)

    total_len = _evidence_text_length(evidence)
    if total_len >= 320:
        score += 1.5
    elif total_len >= 160:
        score += 0.8

    blob = " ".join(
        item.get("quote", "") if isinstance(item, dict) else str(item or "")
        for item in evidence
    )
    if _NUMBER_RE.search(blob):
        score += 0.7
    if _PRODUCT_RE.search(blob):
        score += 0.5

    if cross >= 2:
        score += 1.5
    if cross >= 3:
        score += 1.0

    if signal.get("actors"):
        score += 0.3

    score = max(0.0, min(IMPORTANCE_MAX["evidence_strength"], score))
    return score, (
        f"подтверждений: {len(evidence)}, объём цитат: {total_len} симв., "
        f"источников в кластере: {cross}"
    )


def compute_user_or_market_impact(signal: dict) -> tuple[float, str]:
    """0–5. Closer to a bank/user scenario = higher."""
    score = 0.0
    if signal.get("user_scenario"):
        score += 1.5
    if signal.get("event_type") in {"launch", "ux_change", "regulation"}:
        score += 1.5
    if signal.get("product_area") in {"payments", "banking"}:
        score += 1.0
    elif signal.get("product_area") in {"embedded_finance", "identity"}:
        score += 0.7
    if (signal.get("category") or "") == "Партнёрство":
        score += 0.5
    if signal.get("geography") in {"United Kingdom", "European Union", "Global"}:
        score += 0.3
    score = max(0.0, min(IMPORTANCE_MAX["user_or_market_impact"], score))
    scenario_tag = "есть пользовательский сценарий" if signal.get("user_scenario") else "сценарий не выделен"
    return score, f"{scenario_tag}, тип события: {_ru_event(signal.get('event_type'))}"


def _level_label(value: int) -> str:
    if value <= 30:  return "шум"
    if value <= 55:  return "низкая"
    if value <= 75:  return "средняя"
    if value <= 90:  return "высокая"
    return "критичная"


def compute_importance(signal: dict) -> tuple[int, dict, str]:
    """Returns (importance 0-100, breakdown dict of integers, human reason)."""
    factors = {
        "bank_relevance": compute_bank_relevance(signal),
        "signal_type_weight": compute_signal_type_weight(signal),
        "novelty": compute_novelty(signal),
        "source_quality": compute_source_quality(signal),
        "recency": compute_recency(signal),
        "evidence_strength": compute_evidence_strength(signal),
        "user_or_market_impact": compute_user_or_market_impact(signal),
    }

    # Penalties — applied after factors so they shave the total, not the individual.
    penalty = 0.0
    penalty_reasons: list[str] = []
    if signal.get("decision") == "reject" or signal.get("is_noise"):
        penalty += 35.0
        penalty_reasons.append("отброшено фильтром шума")
    text = _gather_text(signal)
    if len(text) < 200:
        penalty += 4.0
        penalty_reasons.append("очень короткий текст")
    if signal.get("source_type") == "reprint" and (signal.get("cross_source_count") or 1) <= 1:
        penalty += 6.0
        penalty_reasons.append("одиночная перепечатка")

    # Round each factor to .1 so the SUM has fine granularity
    breakdown = {key: round(value, 1) for key, (value, _why) in factors.items()}
    raw_total = sum(breakdown.values()) - penalty
    importance = max(0, min(100, round(raw_total)))

    breakdown_int = {key: round(value) for key, (value, _why) in factors.items()}
    # ensure integer breakdown sums close to importance for the UI
    reasons_parts: list[str] = []
    top = sorted(factors.items(), key=lambda kv: kv[1][0], reverse=True)
    for key, (_value, why) in top[:2]:
        reasons_parts.append(f"{key}: {why}")
    if penalty_reasons:
        reasons_parts.append("штрафы: " + ", ".join(penalty_reasons))
    reason = "; ".join(reasons_parts) or "оценка по продуктовым факторам"

    breakdown_int["_level"] = _level_label(importance)
    return importance, breakdown_int, reason


# ─── Confidence ────────────────────────────────────────────────────────────

CONFIDENCE_WEIGHTS = {
    "has_valid_title": 0.10,
    "has_publication_date": 0.10,
    "extraction_quality": 0.15,
    "source_reliability": 0.15,
    "has_primary_source": 0.10,
    "cross_source_confirmation": 0.10,
    "entity_extraction_quality": 0.10,
    "llm_json_validity": 0.10,
    "duplicate_or_repost_penalty": -0.10,
    "weak_content_penalty": -0.10,
}


def _host_from_url(url: str) -> str:
    if not url:
        return ""
    raw = str(url).lower()
    raw = re.sub(r"^https?://", "", raw)
    return raw.split("/", 1)[0]


_CONCRETE_EVENT_RE = re.compile(
    r"\b(launch(ed|es)?|introduce[sd]?|rolls? out|unveil(ed|s)?|"
    r"partnership|partner with|регулирован|запуст\w*|представ\w*|выпуст\w*|"
    r"обнов\w*|партн[её]рств\w*|утверд\w*|объяв\w*|внедр\w*|подключ\w*)\b",
    re.IGNORECASE,
)


def _concrete_event_signal(signal: dict, text_l: str) -> float:
    """0.0–1.0. Whether the article describes a concrete event (launch, regulation, partnership)."""
    event_type = signal.get("event_type", "other")
    weight = {
        "launch": 1.0,
        "regulation": 1.0,
        "ux_change": 0.85,
        "partnership": 0.85,
        "market_signal": 0.50,
        "other": 0.0,
    }.get(event_type, 0.0)
    if weight == 0.0 and _CONCRETE_EVENT_RE.search(text_l):
        weight = 0.5
    if signal.get("user_scenario"):
        weight = min(1.0, weight + 0.10)
    return weight


def compute_confidence(signal: dict) -> tuple[float, dict, str]:
    """0.05–0.98. Reflects trust in the card, not the LLM's self-confidence.

    Per-article variation comes from many small features so two articles with
    different bodies / sources / events don't collapse to the same value.
    No randomness: every input is a measurable property of the article.
    """
    title = str(signal.get("title") or signal.get("headline") or "").strip()
    text = _gather_text(signal)
    text_l = text.lower()
    text_len = len(text)
    evidence = signal.get("evidence") or []
    cross = max(1, int(signal.get("cross_source_count") or len(signal.get("sources") or []) or 1))
    source_type = signal.get("source_type", "unknown")
    actors = signal.get("actors") or []
    url = signal.get("url") or ""

    has_valid_title = 1.0 if (len(title) >= 12 and not title.lower().startswith("untitled")) else 0.0
    has_publication_date = 1.0 if (signal.get("published_at") or signal.get("date")) else 0.0

    # extraction_quality: smooth growth up to ~1600 chars, plus evidence bonus.
    # The previous /800 saturated very quickly and made every long noise item identical.
    extraction_quality = min(1.0, text_len / 1600.0)
    if evidence:
        extraction_quality = min(1.0, extraction_quality + 0.10)
    # account for evidence text length too (per-article variation)
    ev_chars = _evidence_text_length(evidence)
    if ev_chars >= 300:
        extraction_quality = min(1.0, extraction_quality + 0.05)

    # source_reliability: start from source_type but elevate if URL is on the
    # trusted-media whitelist even when source_type is "unknown" (common for
    # raw Firecrawl results without enrichment).
    base_reliability = {
        "primary": 0.92,
        "trusted_media": 0.75,
        "unknown": 0.45,
        "reprint": 0.30,
    }.get(source_type, 0.40)
    host = _host_from_url(url)
    if host and any(domain in host for domain in TRUSTED_MEDIA_DOMAINS):
        base_reliability = max(base_reliability, 0.72)
    # tiny per-article adjustment from source_score if available
    source_score = signal.get("source_score")
    if isinstance(source_score, (int, float)):
        # nudge ±0.05 based on a 0–100 score
        base_reliability = max(0.10, min(0.98, base_reliability + (float(source_score) - 50.0) / 1000.0))
    source_reliability = base_reliability

    has_primary_source = 1.0 if source_type == "primary" else 0.0
    cross_source_confirmation = 0.0 if cross <= 1 else min(1.0, (cross - 1) / 3.0)

    entity_quality = min(1.0, len(actors) / 3.0) if actors else 0.0

    if signal.get("llm_fallback"):
        llm_json_validity = 0.5
    elif signal.get("llm_used"):
        llm_json_validity = 1.0
    else:
        llm_json_validity = 0.7

    # New: fintech anchor density (per-article variation, helps even when
    # source/actors are empty for rejected items).
    anchor_hits = _count_fintech_anchors(text_l)
    anchor_density = min(1.0, anchor_hits / 8.0)

    # New: concrete-event signal (launch / regulation / partnership / ...).
    concrete_event = _concrete_event_signal(signal, text_l)

    # New: relevance classifier certainty. The relevance gate stores its own
    # confidence under `relevance_confidence`; if missing, fall back to 0.5.
    relevance_certainty = signal.get("relevance_confidence")
    if not isinstance(relevance_certainty, (int, float)):
        relevance_certainty = 0.5
    relevance_certainty = max(0.0, min(1.0, float(relevance_certainty)))

    duplicate_penalty = 1.0 if (source_type == "reprint" and cross <= 1) else 0.0
    weak_content_penalty = 1.0 if text_len < 240 else (0.5 if text_len < 480 else 0.0)

    breakdown = {
        "has_valid_title": bool(has_valid_title),
        "has_publication_date": bool(has_publication_date),
        "extraction_quality": round(extraction_quality, 2),
        "source_reliability": round(source_reliability, 2),
        "has_primary_source": bool(has_primary_source),
        "cross_source_confirmation": round(cross_source_confirmation, 2),
        "entity_extraction_quality": round(entity_quality, 2),
        "llm_json_validity": round(llm_json_validity, 2),
        "fintech_anchor_density": round(anchor_density, 2),
        "concrete_event_signal": round(concrete_event, 2),
        "relevance_certainty": round(relevance_certainty, 2),
        "duplicate_or_repost_penalty": round(duplicate_penalty * 0.10, 2),
        "weak_content_penalty": round(weak_content_penalty * 0.08, 2),
    }

    # Weights rebalanced so the sum of positive maxes is ≈ 1.0 (with the 0.05
    # baseline + small bonuses). Reject items still scale down at the end.
    raw = (
        0.05
        + 0.08 * has_valid_title
        + 0.07 * has_publication_date
        + 0.13 * extraction_quality
        + 0.14 * source_reliability
        + 0.08 * has_primary_source
        + 0.10 * cross_source_confirmation
        + 0.08 * entity_quality
        + 0.08 * llm_json_validity
        + 0.08 * anchor_density
        + 0.10 * concrete_event
        + 0.06 * relevance_certainty
        - 0.10 * duplicate_penalty
        - 0.08 * weak_content_penalty
    )

    # Rejected items scale down — preserves per-article variation instead of
    # collapsing every reject to one number.
    is_reject = signal.get("decision") == "reject" or signal.get("is_noise")
    if is_reject:
        # For rejects, the relevance classifier itself was confident → that
        # belief INVERSELY affects how much we should trust the card as a signal.
        raw = (raw * 0.55) - 0.05 * relevance_certainty
        # No concrete event in noise → push it lower
        if concrete_event <= 0.0:
            raw -= 0.04

    confidence = max(0.05, min(0.98, raw))

    reasons: list[str] = []
    if not has_valid_title:
        reasons.append("слабый или отсутствующий заголовок")
    if not has_publication_date:
        reasons.append("нет даты публикации")
    if text_len < 240:
        reasons.append("очень короткий текст")
    elif text_len < 480:
        reasons.append("короткий текст")
    if source_reliability >= 0.72:
        reasons.append("надёжный источник")
    if has_primary_source:
        reasons.append("есть первоисточник")
    if cross >= 2:
        reasons.append(f"подтверждено {cross} источниками")
    if duplicate_penalty:
        reasons.append("одиночная перепечатка без новых фактов")
    if anchor_hits >= 4:
        reasons.append(f"плотный финтех-контекст ({anchor_hits} терминов)")
    elif anchor_hits == 0 and not is_reject:
        reasons.append("нет финтех-якорей")
    if concrete_event >= 0.85:
        reasons.append("описано конкретное событие")
    elif concrete_event == 0.0 and not is_reject:
        reasons.append("конкретное событие не выявлено")
    if signal.get("llm_fallback"):
        reasons.append("LLM упала, использован rule-based fallback")
    reason = "; ".join(reasons) if reasons else "стандартные параметры"

    return round(confidence, 2), breakdown, reason


# ─── Dev log ───────────────────────────────────────────────────────────────

def _dev_log_enabled() -> bool:
    return os.environ.get("TW_SCORING_DEBUG", "").lower() in {"1", "true", "yes"}


@dataclass
class DevTrace:
    url: str
    title: str
    importance: int
    confidence: float
    importance_breakdown: dict
    confidence_breakdown: dict
    fallback_reason: str
    scoring_version: str

    def log(self) -> None:
        if not _dev_log_enabled():
            return
        print(
            f"[scoring v2] url={self.url[:80]!r} title={self.title[:80]!r} "
            f"importance={self.importance} confidence={self.confidence} "
            f"fallback={self.fallback_reason or '—'}"
        )
