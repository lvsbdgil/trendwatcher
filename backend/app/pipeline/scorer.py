"""Signal scoring — uses quality_scorer v2 for importance + confidence.

Backward compatibility:
- `hotness` is kept as an alias of `importance` (existing UI reads `hotness`);
- `score_explanation` keeps the old shape (one entry per factor with score/why);
- legacy fields untouched, new fields added on top.
"""
from .noise_filter import SIGNAL_THRESHOLD, assess_signal_noise, signal_has_evidence
from .quality_scorer import (
    DevTrace,
    IMPORTANCE_MAX,
    SCORING_VERSION,
    compute_bank_relevance,
    compute_confidence,
    compute_evidence_strength,
    compute_importance,
    compute_novelty,
    compute_recency,
    compute_signal_type_weight,
    compute_source_quality,
    compute_user_or_market_impact,
)


def score_signals(signals, top_n=5):
    scored = [score_signal(signal) for signal in signals]
    selected = [
        signal
        for signal in scored
        if signal.get("decision") == "keep"
        and not signal.get("is_noise")
        and signal.get("hotness", 0) >= SIGNAL_THRESHOLD
        and signal.get("confidence", 0) >= 0.45
        and signal.get("evidence")
        and signal_has_evidence(signal)
        and signal.get("score_explanation")
    ]
    selected = sorted(selected, key=lambda signal: signal.get("hotness", 0), reverse=True)[:top_n]
    return scored, selected


def score_signal(signal):
    noise = assess_signal_noise(signal)
    is_rejected = (
        signal.get("decision") == "reject"
        or signal.get("is_noise")
        or noise["is_noise"]
    )

    if is_rejected:
        reason = (
            signal.get("rejection_reason")
            or signal.get("reject_reason")
            or noise["reason"]
            or "not enough evidence for a fintech signal"
        )
        signal = {**signal, "decision": "reject", "is_noise": True}
        importance, importance_bd, importance_reason = compute_importance(signal)
        confidence, confidence_bd, confidence_reason = compute_confidence(signal)
        score_explanation = _legacy_explanation(signal, importance_bd, reason)
        DevTrace(
            url=signal.get("url", ""),
            title=signal.get("title", ""),
            importance=importance,
            confidence=confidence,
            importance_breakdown=importance_bd,
            confidence_breakdown=confidence_bd,
            fallback_reason="rejected: " + reason,
            scoring_version=SCORING_VERSION,
        ).log()
        return {
            **signal,
            "decision": "reject",
            "is_noise": True,
            "rejection_reason": reason,
            "reject_reason": reason,
            "category": noise.get("category") or signal.get("category") or "Шум / нерелевантное",
            "hotness": importance,
            "importance": importance,
            "importance_breakdown": importance_bd,
            "importance_reason": importance_reason,
            "confidence": confidence,
            "confidence_breakdown": confidence_bd,
            "confidence_reason": confidence_reason,
            "scoring_version": SCORING_VERSION,
            "score_explanation": signal.get("score_explanation") or score_explanation,
        }

    importance, importance_bd, importance_reason = compute_importance(signal)
    confidence, confidence_bd, confidence_reason = compute_confidence(signal)
    score_explanation = _legacy_explanation(signal, importance_bd, "штрафов нет")

    DevTrace(
        url=signal.get("url", ""),
        title=signal.get("title", ""),
        importance=importance,
        confidence=confidence,
        importance_breakdown=importance_bd,
        confidence_breakdown=confidence_bd,
        fallback_reason="" if not signal.get("llm_fallback") else "LLM fallback",
        scoring_version=SCORING_VERSION,
    ).log()

    return {
        **signal,
        "is_noise": False,
        "hotness": importance,
        "importance": importance,
        "importance_breakdown": importance_bd,
        "importance_reason": importance_reason,
        "confidence": confidence,
        "confidence_breakdown": confidence_bd,
        "confidence_reason": confidence_reason,
        "scoring_version": SCORING_VERSION,
        "score_explanation": score_explanation,
    }


def score_articles(articles):
    """Backward-compatible wrapper for older UI paths."""
    return [score_signal(article) for article in articles]


def calculate_source_credibility(article):
    return int(article.get("source_score") or 60)


def _legacy_explanation(signal, importance_breakdown, penalty_text):
    """Reconstruct the old per-factor explanation for backward compat in the UI."""
    factor_pairs = [
        ("bank_relevance", compute_bank_relevance),
        ("signal_type_weight", compute_signal_type_weight),
        ("novelty", compute_novelty),
        ("source_quality", compute_source_quality),
        ("recency", compute_recency),
        ("evidence_strength", compute_evidence_strength),
        ("user_or_market_impact", compute_user_or_market_impact),
    ]
    explanation = {}
    for key, fn in factor_pairs:
        value, why = fn(signal)
        explanation[key] = {
            "score": round(value),
            "max": IMPORTANCE_MAX.get(key),
            "why": why,
        }
    explanation["penalties"] = {"score": 0, "why": penalty_text}
    return explanation
