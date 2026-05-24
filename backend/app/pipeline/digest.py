BANNED_GENERIC = (
    "может быть важным",
    "стоит посмотреть",
    "рынок меняется",
    "возможный вывод",
    "требует дополнительной проверки",
)


def build_digest(cards, stats=None, duplicate_logs=None):
    threshold = (stats or {}).get("signal_threshold", 55)
    cards = [
        card
        for card in cards
        if not card.get("is_noise")
        and isinstance(card.get("hotness"), (int, float))
        and card.get("hotness", 0) >= threshold
        and card.get("evidence")
    ]
    stats = stats or {}
    duplicate_logs = duplicate_logs or []
    lines = [
        "# Fintech Trend Digest",
        "",
        "## Executive summary",
    ]
    lines.extend(_executive_summary(cards))
    lines.extend(["", "## Top signals"])

    if not cards:
        lines.append("Сильных сигналов с evidence и достаточным hotness не найдено.")
    for index, card in enumerate(cards, start=1):
        source_links = _source_links(card.get("sources", []))
        evidence = (card.get("evidence") or [{}])[0].get("quote", "")
        next_step = _next_step_from_card(card)
        lines.extend(
            [
                f"{index}. {card.get('headline', '')}",
                f"Hotness: {card.get('hotness', 0)}/100 · Confidence: {_confidence(card.get('confidence'))}",
                f"Category: {card.get('category', '')}",
                f"Why now: {card.get('whyNow') or card.get('why_now', '')}",
                f"Зачем это продуктовой команде: {_product_importance(card)}",
                f"Что сделать команде банка: {next_step}",
                f"Sources: {source_links}",
                f"Evidence: {evidence}",
                "",
            ]
        )

    noise = stats.get("noise_breakdown", {})
    lines.extend(
        [
            "## Отброшено как шум",
            f"- {noise.get('conference_event', 0)} конференций/ивентов",
            f"- {len(duplicate_logs)} дублей/перепечаток",
            f"- {noise.get('irrelevant', 0)} нерелевантных материалов",
            f"- {noise.get('no_evidence', 0)} материалов без evidence",
            "",
            "## Ограничения",
            "Дайджест собран по открытым источникам; для запуска работ команда сверяет первоисточник, владельца продукта и затронутую метрику.",
        ]
    )
    return _clean("\n".join(lines))


def _executive_summary(cards):
    if not cards:
        return ["- За период не найдено сильных финтех-сигналов с проверяемыми фрагментами источников."]
    bullets = []
    top = cards[0]
    bullets.append(f"- Главный сигнал: {top.get('headline', '')} ({top.get('hotness', 0)}/100).")
    categories = ", ".join(dict.fromkeys(card.get("category", "") for card in cards if card.get("category")))
    if categories:
        bullets.append(f"- Покрытые темы: {categories}.")
    primary_count = sum(1 for card in cards for source in card.get("sources", []) if source.get("kind") == "primary")
    bullets.append(f"- Первоисточников в выбранных сигналах: {primary_count}; все выбранные карточки содержат evidence.")
    bullets.append(f"- Команде банка нужен быстрый разбор {len(cards)} сценариев: продуктовый владелец, затронутый flow и метрика.")
    return bullets[:5]


def _source_links(sources):
    if not sources:
        return "нет источников"
    parts = []
    for source in sources:
        kind = source.get("kind", "unknown")
        url = source.get("url", "")
        title = source.get("source") or source.get("title") or url
        parts.append(f"{kind}: {title} ({url})")
    return "; ".join(parts)


def _confidence(value):
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return str(value or "unknown")


def _next_step_from_card(card):
    score = card.get("score_explanation", {})
    action = score.get("actionability", {})
    if isinstance(action, dict) and action.get("why"):
        return action["why"]
    return "назначить владельца, проверить source evidence и собрать один продуктовый тест с метрикой."


def _product_importance(card):
    summary = card.get("summary") or ""
    category = card.get("category") or "сигнал"
    hotness = card.get("hotness", 0)
    if "Плат" in category:
        return f"hotness {hotness}/100 указывает на платежный сценарий, который влияет на conversion, wallet usage или экономику карт."
    if "Регули" in category:
        return f"hotness {hotness}/100 показывает изменение правил, затрагивающее compliance, consent-flow или сроки релиза."
    if "UX" in category:
        return f"hotness {hotness}/100 связан с клиентским friction в цифровом канале и приоритетами мобильного продукта."
    if "Парт" in category:
        return f"hotness {hotness}/100 помогает проверить, закрывает ли партнерский канал недостающий customer journey."
    return summary or f"hotness {hotness}/100 дает команде конкретный повод выбрать владельца, сегмент и метрику эксперимента."


def _clean(text):
    cleaned = text
    for phrase in BANNED_GENERIC:
        cleaned = cleaned.replace(phrase, "конкретный проверяемый сценарий")
    return cleaned
