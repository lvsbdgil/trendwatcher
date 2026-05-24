import re


BANNED_REPLACEMENTS = {
    "может быть важным": "даёт проверяемый продуктовый сигнал",
    "стоит посмотреть": "сравните с текущим продуктовым сценарием",
    "рынок меняется": "появился новый проверяемый пример",
    "требует дополнительной проверки": "сверьте источник и затронутый сценарий",
    "возможный вывод: проверить, применим ли": "следующий шаг: сравнить сценарий с",
    "возможный вывод": "следующий шаг",
}


def make_rule_based_card(signal):
    headline = _clean(signal.get("headline") or signal.get("title", ""))
    hotness = int(signal.get("hotness", 0) or 0)
    category = signal.get("category", "Рынок")
    evidence = signal.get("evidence") or []
    sources = signal.get("sources") or [_source_from_signal(signal)]
    summary_fact = _clean(signal.get("summary_fact") or (evidence[0]["quote"] if evidence else headline))
    bank_relevance = _clean(signal.get("bank_relevance") or "Assign an owner to benchmark this scenario against the product roadmap.")
    next_step = _next_step(signal)
    why_now = _clean(f"{summary_fact} Для банка следующий шаг: {next_step}")
    summary = _clean(_summary(signal, summary_fact))
    draft = _clean(_draft(signal, headline, summary_fact, bank_relevance, next_step))

    card = {
        "headline": headline,
        "title": headline,
        "url": signal.get("url", ""),
        "source": signal.get("source", "Unknown"),
        "hotness": hotness,
        "importance": signal.get("importance", hotness),
        "importance_breakdown": signal.get("importance_breakdown", {}),
        "importance_reason": signal.get("importance_reason", ""),
        "category": category,
        "why_now": why_now,
        "whyNow": why_now,
        "sources": sources,
        "summary": summary,
        "draft": draft,
        "confidence": signal.get("confidence", 0),
        "confidence_breakdown": signal.get("confidence_breakdown", {}),
        "confidence_reason": signal.get("confidence_reason", ""),
        "evidence": evidence,
        "score_explanation": signal.get("score_explanation", {}),
        "is_noise": bool(signal.get("is_noise", False)),
        "rejection_reason": signal.get("rejection_reason", ""),
        "scoring_version": signal.get("scoring_version", ""),
        "is_duplicate": bool(signal.get("is_duplicate", False)),
        "duplicate_cluster_id": signal.get("duplicate_cluster_id", ""),
        "primary_source_url": signal.get("primary_source_url", ""),
        "duplicate_count": signal.get("duplicate_count", 0),
    }
    if signal.get("duplicate_group"):
        card["duplicate_group"] = signal["duplicate_group"]
    return card


def _summary(signal, summary_fact):
    scenario = signal.get("user_scenario") or "банковский сценарий"
    relevance = signal.get("bank_relevance", "")
    return f"{summary_fact} Сценарий для банка: {scenario}. {relevance}"


def _draft(signal, headline, summary_fact, bank_relevance, next_step):
    source_names = ", ".join(source.get("source", "") for source in signal.get("sources", [])[:2] if source.get("source"))
    source_text = f" Источники: {source_names}." if source_names else ""
    return (
        f"{headline}. {summary_fact} {bank_relevance} "
        f"Следующий шаг для команды банка: {next_step}.{source_text}"
    )


def _next_step(signal):
    event_type = signal.get("event_type")
    product_area = signal.get("product_area") or "product"
    if event_type == "regulation":
        return "сопоставить affected flows, владельцев и сроки изменения требований"
    if event_type == "partnership":
        return "сравнить партнёрский канал с текущими интеграциями и метриками активации"
    if event_type == "launch":
        return f"разобрать механику {product_area} и оценить влияние на acquisition, usage или retention"
    if event_type == "ux_change":
        return "собрать UX-разбор экрана или flow и проверить гипотезу на приоритетном клиентском пути"
    return "сформулировать один тест с метрикой, сегментом и владельцем"


def _source_from_signal(signal):
    return {
        "url": signal.get("url", ""),
        "title": signal.get("title") or signal.get("headline", ""),
        "source": signal.get("source", "Unknown"),
        "kind": signal.get("source_type", "unknown"),
    }


def _clean(text):
    cleaned = str(text or "").strip()
    for phrase, replacement in BANNED_REPLACEMENTS.items():
        cleaned = re.sub(re.escape(phrase), replacement, cleaned, flags=re.IGNORECASE)
    return cleaned
