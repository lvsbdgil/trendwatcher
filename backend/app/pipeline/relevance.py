import os
import re

from ..adapters.openai import complete_json, is_available as is_llm_available
from .noise_filter import assess_article_noise, normalize_rejected_item


FINTECH_ANCHORS = (
    # English core
    "bank", "banking", "payment", "payments", "card", "cards", "wallet",
    "loan", "credit", "debit", "mortgage", "deposit", "checkout", "merchant",
    "fintech", "finance", "transfer", "remittance", "transaction",
    "regulator", "regulation", "compliance", "kyc", "aml", "open banking",
    "embedded finance", "baas", "bnpl", "cbdc", "stablecoin", "crypto",
    "exchange", "investment", "insurance", "insurer", "underwriting",
    "issuer", "acquirer", "interchange", "settlement", "neobank", "lending",
    # Russian core
    "банк", "банков", "платеж", "платёж", "платежн",
    "карта", "карты", "карт ", "кошелек", "кошелёк",
    "кредит", "кредитн", "ипотек", "вклад", "депозит", "займ", "заём", "заем",
    "счет", "счёт", "счета", "счёта",
    "перевод", "переводы", "p2p", "сбп",
    "комисси", "тариф", "ставк",
    "финансов", "финтех", "финансы",
    "регулятор", "цб ", "банк россии", "минфин", "фнс",
    "эквайринг", "эмисси", "инкассац",
    "страхов", "инвестиц",
    "криптовалют", "стейблкоин", "цифровой рубль",
    "рассрочк", "bnpl", "кэшбэк", "кешбэк",
    "необанк", "брокер", "биржа", "торги",
    "овердрафт", "рефинансир", "лизинг",
    "микрокредит", "микрофинанс", "мфо",
    "пенсион", "налогов", "налог",
    "ебс", "биометри", "иннн", "снилс",
)

NEGATIVE_HINTS = (
    "конференц", "вебинар", "спикер", "награда", "premiere", "movie",
    "football", "soccer", "tennis", "olympic", "world cup", "recipe",
    "cooking", "celebrity", "marriage", "wedding",
    "футбол", "хоккей", "теннис", "рецепт", "погода", "звезд",
    "сериал", "фильм", "премьер", "концерт",
)

ACTIONABLE_HINTS = (
    "launch", "launched", "launches", "rolls out", "introduced", "introduces",
    "unveiled", "released", "published rules", "requires", "must show",
    "partner", "partnership", "checkout", "wallet", "merchant", "open banking",
    "consent", "card issuing", "lending", "working-capital", "biometric",
    "запустил", "запустила", "запустили", "представил", "представила",
    "выпустил", "выпустила", "опубликовал", "утвердил", "требования",
    "правила", "обязаны", "партнерство", "партнёрство", "сервис",
    "приложение", "кошелек", "кошелёк", "эквайринг", "рассрочка",
)

NOISE_ONLY_HINTS = (
    "conference", "webinar", "speaker lineup", "speaker", "summit", "agenda",
    "award", "awards", "appointed", "appointment", "chief marketing officer",
    "hiring", "vacancy", "podcast",
    "конференц", "вебинар", "спикер", "саммит", "повестка", "награда",
    "премия", "назначен", "назначила", "назначили", "ваканси",
)

FUNDING_ONLY_HINTS = (
    "funding", "raised", "raises", "series a", "seed round", "valuation",
    "инвестиции", "раунд", "привлек", "привлекла", "оценена",
)

WEAK_GENERIC_HINTS = (
    "does not describe", "does not announce", "does not identify",
    "did not announce",
    "no specific product", "no concrete product", "without naming a customer scenario",
    "monitor the market", "brand awareness",
    "не описывает", "не объявляет", "без конкретного продукта",
)


def gate_mode() -> str:
    explicit = os.getenv("RELEVANCE_GATE", "").strip().lower()
    if explicit in {"llm", "rule", "off"}:
        return explicit
    return "llm" if is_llm_available() else "rule"


def assess_relevance(article) -> dict:
    mode = gate_mode()
    if mode == "off":
        return {"is_fintech": True, "confidence": 0.5, "reason": "gate disabled", "method": "off"}

    text = _article_text(article)
    if not text:
        return {"is_fintech": False, "confidence": 0.9, "reason": "empty body", "method": "rule_empty"}

    noise = assess_article_noise(article)
    if noise["is_noise"]:
        return {
            "is_fintech": False,
            "confidence": 0.9,
            "reason": noise["reason"],
            "method": f"rule_noise_{noise['kind']}",
            "noise": noise,
        }

    anchor_hits = _count_anchors(text)
    if anchor_hits == 0:
        return {
            "is_fintech": False,
            "confidence": 0.9,
            "reason": "no fintech terms found in article body",
            "method": "rule_zero_anchor",
        }

    if mode == "rule":
        return _rule_decision(text, anchor_hits)

    llm_result = _llm_classify(article, text)
    if llm_result is not None:
        return llm_result
    return _rule_decision(text, anchor_hits)


def filter_by_relevance(articles) -> tuple[list[dict], list[dict]]:
    relevant: list[dict] = []
    irrelevant: list[dict] = []
    for article in articles:
        verdict = assess_relevance(article)
        if verdict["is_fintech"]:
            relevant.append(article)
            continue
        irrelevant.append(
            normalize_rejected_item({
                "article_id": str(article.get("id") or ""),
                "title": article.get("title", ""),
                "snippet": article.get("snippet", ""),
                "full_text": article.get("full_text", ""),
                "url": article.get("url", ""),
                "source": article.get("source", "Unknown"),
                "source_type": article.get("source_type", "unknown"),
                "published_at": article.get("date", "") or article.get("fetched_at", ""),
                "decision": "reject",
                "reject_reason": f"not fintech topic: noise: {verdict['reason']}" if verdict.get("noise") else f"not fintech topic: {verdict['reason']}",
                "category": "Шум / нерелевантное",
                "event_type": "other",
                "hotness": verdict.get("noise", {}).get("hotness", 0),
                "confidence": round(1.0 - verdict["confidence"], 2),
                "relevance_confidence": float(verdict["confidence"]),
                "evidence": [],
                "sources": [],
                "score_explanation": {},
                "relevance_method": verdict["method"],
            })
        )
    return relevant, irrelevant


def _rule_decision(text: str, anchor_hits: int) -> dict:
    text_l = text.lower()
    negative_hit = next((hint for hint in NEGATIVE_HINTS if hint in text_l), "")
    noise_hit = next((hint for hint in NOISE_ONLY_HINTS if hint in text_l), "")
    funding_hit = next((hint for hint in FUNDING_ONLY_HINTS if hint in text_l), "")
    weak_generic_hit = next((hint for hint in WEAK_GENERIC_HINTS if hint in text_l), "")
    actionable_hits = sum(1 for hint in ACTIONABLE_HINTS if hint in text_l)

    if noise_hit and (actionable_hits == 0 or weak_generic_hit):
        return {
            "is_fintech": False,
            "confidence": 0.88,
            "reason": f"noise item: {noise_hit}",
            "method": "rule_noise",
        }

    if funding_hit and actionable_hits == 0:
        return {
            "is_fintech": False,
            "confidence": 0.78,
            "reason": "funding-only item without product, regulation or customer scenario",
            "method": "rule_funding_noise",
        }

    if weak_generic_hit:
        return {
            "is_fintech": False,
            "confidence": 0.86,
            "reason": f"noise item: generic without concrete product fact: {weak_generic_hit}",
            "method": "rule_generic_noise",
        }

    if anchor_hits >= 2 and actionable_hits >= 1 and not negative_hit:
        return {
            "is_fintech": True,
            "confidence": 0.7,
            "reason": f"{anchor_hits} fintech terms and {actionable_hits} concrete action marker(s) found",
            "method": "rule",
        }

    if anchor_hits >= 3 and not noise_hit:
        return {
            "is_fintech": True,
            "confidence": 0.75,
            "reason": f"{anchor_hits} fintech terms despite negative marker",
            "method": "rule",
        }

    if negative_hit or noise_hit:
        return {
            "is_fintech": False,
            "confidence": 0.76,
            "reason": f"finance term appears in non-actionable context: {negative_hit or noise_hit}",
            "method": "rule_context_noise",
        }

    return {
        "is_fintech": False,
        "confidence": 0.6,
        "reason": f"only {anchor_hits} fintech anchor(s) without supporting context",
        "method": "rule",
    }


def _llm_classify(article, text: str) -> dict | None:
    system_prompt = (
        "Ты классификатор финтех-публикаций для внутреннего дайджеста банка. "
        "Верни валидный JSON {\"is_fintech\": true|false, \"reason\": \"<одно короткое предложение>\"}. "
        "Не возвращай ничего кроме JSON."
    )
    user_prompt = (
        "Определи, относится ли публикация к финтех-/банковской сфере.\n"
        "FINTECH = банки, платежи, карты, кредиты, ипотека, депозиты, инвестиции, страхование, "
        "регулирование финрынка, цифровые валюты, BNPL, эквайринг, открытый банкинг, налоги, пенсии.\n"
        "NOT FINTECH = спорт, развлечения, погода, рецепты, кино, общая политика без финповестки, "
        "кадровые назначения, конференции, общий PR без финансового продукта.\n\n"
        f"Заголовок: {article.get('title', '')}\n"
        f"Источник: {article.get('source', '')}\n"
        f"Текст:\n{text[:1500]}"
    )
    result = complete_json(system_prompt, user_prompt, max_tokens=120, temperature=0.0)
    if not isinstance(result, dict):
        return None
    if "is_fintech" not in result:
        return None
    is_fintech = bool(result.get("is_fintech"))
    reason = str(result.get("reason") or "").strip()[:240] or ("fintech-relevant" if is_fintech else "not relevant")
    return {
        "is_fintech": is_fintech,
        "confidence": 0.9,
        "reason": reason,
        "method": "llm",
    }


def _article_text(article) -> str:
    parts = [
        article.get("title", ""),
        article.get("snippet", ""),
        article.get("full_text", ""),
        article.get("markdown", ""),
    ]
    text = " ".join(str(part or "") for part in parts)
    return re.sub(r"\s+", " ", text).strip()


def _count_anchors(text: str) -> int:
    text_l = text.lower()
    hits = 0
    for anchor in FINTECH_ANCHORS:
        if anchor in text_l:
            hits += 1
            if hits >= 5:
                return hits
    return hits
