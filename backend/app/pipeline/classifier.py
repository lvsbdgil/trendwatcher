CATEGORIES = {
    "Банковский продукт": [
        "bank",
        "banking",
        "account",
        "deposit",
        "loan",
        "credit",
        "debit",
        "cashback",
        "savings",
        "personal finance",
    ],
    "Платёжный сервис": [
        "payment",
        "payments",
        "card",
        "cards",
        "checkout",
        "wallet",
        "transfer",
        "virtual card",
        "merchant",
    ],
    "UX-механика": [
        "assistant",
        "ai assistant",
        "experience",
        "flow",
        "interface",
        "mobile",
        "personalization",
        "conversion",
    ],
    "Партнёрство": [
        "partner",
        "partners",
        "partnership",
        "collaboration",
        "teams up",
        "alliance",
    ],
    "Регулирование": [
        "regulator",
        "regulation",
        "rules",
        "guidance",
        "compliance",
        "license",
        "law",
        "open banking",
    ],
    "Рынок": [
        "market",
        "trend",
        "growth",
        "adoption",
        "industry",
        "report",
    ],
}

NOISE_KEYWORDS = [
    "speaker lineup",
    "conference agenda",
    "webinar",
    "award",
    "hiring",
    "appointed",
    "event",
    "podcast",
]


def classify_article(article):
    text = f"{article.get('title', '')} {article.get('snippet', '')}".lower()

    noise_hits = sum(1 for keyword in NOISE_KEYWORDS if keyword in text)
    if noise_hits >= 2:
        return "Шум / нерелевантное"

    scores = {}
    for category, keywords in CATEGORIES.items():
        scores[category] = sum(1 for keyword in keywords if keyword in text)

    best_category = max(scores, key=scores.get)
    if scores[best_category] == 0:
        return "Шум / нерелевантное"

    return best_category


def classify_articles(articles):
    classified = []
    for article in articles:
        enriched = {**article, "category": classify_article(article)}
        classified.append(enriched)
    return classified
