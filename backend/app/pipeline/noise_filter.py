import re


SIGNAL_THRESHOLD = 55

NOISE_CATEGORY = "Шум / нерелевантное"
PR_CATEGORY = "PR / кадровое"

NOISE_PATTERNS = (
    ("conference_event", ("conference", "speaker lineup", "speaker", "webinar", "summit", "agenda", "event announcement")),
    ("award_or_pr", ("award", "wins award", "awards", "generic pr")),
    ("people_move", ("appoints", "appointed", "appointment", "hired", "chief marketing officer", "ceo interview")),
    ("funding_only", ("funding raised", "raises funding", "raised funding", "seed funding", "series a")),
    ("generic_market", ("market will grow", "will keep growing", "market report", "adoption will keep growing")),
)

STRONG_SIGNAL_PATTERNS = (
    "launches",
    "launched",
    "introduces",
    "introduced",
    "rolls out",
    "partners with",
    "embedded finance",
    "wallet",
    "checkout",
    "biometric payment",
    "biometric",
    "open banking",
    "instant payments",
    "consumer protection rules",
    "lending",
    "working capital",
    "working-capital",
    "sme finance",
    "merchant acquiring",
    "fraud prevention",
    "kyc",
    "aml",
    "regulation",
    "rules",
    "guidance",
)

CONCRETE_EVIDENCE_PATTERNS = (
    r"\b\d+(?:[.,]\d+)?\s?%",
    r"\b\d+(?:[.,]\d+)?\s?(?:million|billion|m|bn)\b",
    r"\b(united states|united kingdom|uk|us|eu|european union|global)\b",
    r"\b(merchant|merchants|sme|small business|consumer|customer|bank|provider|users)\b",
    r"\b(launch(?:ed|es)?|introduc(?:ed|es)|rolls out|published|requires|must|partners with)\b",
)


def article_text(article) -> str:
    parts = [
        article.get("title", ""),
        article.get("snippet", ""),
        article.get("full_text", ""),
        article.get("markdown", ""),
    ]
    return _compact(" ".join(str(part or "") for part in parts))


def assess_noise_text(text: str) -> dict:
    text_l = _compact(text).lower()
    if not text_l:
        return {
            "is_noise": True,
            "kind": "empty",
            "category": NOISE_CATEGORY,
            "hotness": 0,
            "confidence_cap": 0.35,
            "reason": "Empty article body",
        }

    strong_hit = _first_hit(text_l, STRONG_SIGNAL_PATTERNS)
    noise_kind, noise_hit = _first_noise_hit(text_l)
    explicit_no_fact = _explicitly_says_no_product_fact(text_l)
    generic_market = _is_generic_market_report(text_l)

    if noise_kind == "conference_event" and (explicit_no_fact or not strong_hit):
        return {
            "is_noise": True,
            "kind": noise_kind,
            "category": NOISE_CATEGORY,
            "hotness": 10,
            "confidence_cap": 0.45,
            "reason": "Конференция/ивент, нет продуктового запуска, банковского сценария или регуляторного изменения",
            "matched": noise_hit,
        }

    if noise_kind in {"award_or_pr", "people_move"} and (explicit_no_fact or not strong_hit):
        return {
            "is_noise": True,
            "kind": noise_kind,
            "category": PR_CATEGORY,
            "hotness": 15,
            "confidence_cap": 0.45,
            "reason": "кадровое назначение/награда без продуктового запуска, нового банковского сценария или регуляторного изменения",
            "matched": noise_hit,
        }

    if noise_kind == "funding_only" and (explicit_no_fact or not strong_hit):
        return {
            "is_noise": True,
            "kind": noise_kind,
            "category": NOISE_CATEGORY,
            "hotness": 20,
            "confidence_cap": 0.5,
            "reason": "funding raised without product launch, banking scenario or regulatory change",
            "matched": noise_hit,
        }

    if generic_market or (noise_kind == "generic_market" and not has_concrete_evidence_text(text_l)):
        return {
            "is_noise": True,
            "kind": "generic_market",
            "category": NOISE_CATEGORY,
            "hotness": 25,
            "confidence_cap": 0.55,
            "reason": "generic market report without concrete figures, region, user behavior, banking scenario or product evidence",
            "matched": noise_hit or "generic market report",
        }

    return {
        "is_noise": False,
        "kind": "",
        "category": "",
        "hotness": None,
        "confidence_cap": 1.0,
        "reason": "",
    }


def assess_article_noise(article) -> dict:
    return assess_noise_text(article_text(article))


def assess_signal_noise(signal) -> dict:
    text = " ".join(
        str(signal.get(key, "") or "")
        for key in ("title", "headline", "summary_fact", "bank_relevance", "reject_reason", "category")
    )
    evidence_text = " ".join(_evidence_quote(item) for item in signal.get("evidence") or [])
    return assess_noise_text(f"{text} {evidence_text}")


def has_concrete_evidence_text(text: str) -> bool:
    text_l = _compact(text).lower()
    if not text_l:
        return False
    hits = sum(1 for pattern in CONCRETE_EVIDENCE_PATTERNS if re.search(pattern, text_l))
    return hits >= 2


def signal_has_evidence(signal) -> bool:
    evidence = signal.get("evidence") or []
    return any(len(_evidence_quote(item)) >= 20 for item in evidence)


def normalize_rejected_item(item, fallback_reason: str = "") -> dict:
    normalized = dict(item)
    text = " ".join(
        str(normalized.get(key, "") or "")
        for key in ("title", "headline", "summary_fact", "reject_reason", "rejection_reason")
    )
    noise = assess_noise_text(text)
    reason = (
        normalized.get("rejection_reason")
        or normalized.get("reject_reason")
        or noise.get("reason")
        or fallback_reason
        or "not enough evidence for a fintech signal"
    )
    hotness = normalized.get("hotness")
    if not isinstance(hotness, (int, float)):
        hotness = noise.get("hotness")
    if not isinstance(hotness, (int, float)):
        hotness = 0
    hotness = max(0, min(40, round(hotness)))
    confidence = normalized.get("confidence")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.35
    confidence = min(confidence, noise.get("confidence_cap", 0.55), 0.55)

    normalized.update(
        {
            "decision": "reject",
            "is_noise": True,
            "rejection_reason": reason,
            "reject_reason": reason,
            "category": noise.get("category") or normalized.get("category") or NOISE_CATEGORY,
            "hotness": hotness,
            "confidence": round(max(0.0, confidence), 2),
            "score_explanation": normalized.get("score_explanation") or _noise_score_explanation(reason, hotness),
            "sources": normalized.get("sources") or [_source_from_item(normalized)],
        }
    )
    return normalized


def _noise_score_explanation(reason: str, hotness: int) -> dict:
    return {
        "noise_filter": {
            "score": hotness,
            "why": reason,
        }
    }


def _source_from_item(item) -> dict:
    return {
        "url": item.get("url", ""),
        "title": item.get("title") or item.get("headline", ""),
        "source": item.get("source", "Unknown"),
        "kind": item.get("source_type", "unknown"),
    }


def _first_noise_hit(text_l: str) -> tuple[str, str]:
    for kind, patterns in NOISE_PATTERNS:
        hit = _first_hit(text_l, patterns)
        if hit:
            return kind, hit
    return "", ""


def _first_hit(text_l: str, patterns) -> str:
    return next((pattern for pattern in patterns if pattern in text_l), "")


def _explicitly_says_no_product_fact(text_l: str) -> bool:
    phrases = (
        "does not announce a product",
        "does not describe a product",
        "does not identify a concrete product",
        "no specific product",
        "no concrete product",
        "without naming a customer scenario",
        "rather than a banking customer scenario",
        "without product impact",
    )
    return any(phrase in text_l for phrase in phrases)


def _is_generic_market_report(text_l: str) -> bool:
    generic = ("market report", "adoption will keep growing", "will keep growing", "monitor the market")
    no_fact = (
        "no specific product",
        "does not identify",
        "does not announce",
        "without naming a customer scenario",
        "broad phrases",
    )
    return any(phrase in text_l for phrase in generic) and (
        any(phrase in text_l for phrase in no_fact) or not has_concrete_evidence_text(text_l)
    )


def _evidence_quote(item) -> str:
    if isinstance(item, dict):
        return str(item.get("quote") or "")
    return str(item or "")


def _compact(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()
