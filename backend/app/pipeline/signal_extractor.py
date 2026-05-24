import hashlib
import json
import re
from urllib.parse import urlsplit

from ..adapters.openai import complete_json, is_available as is_llm_available
from .logging import AnalysisLogger
from .noise_filter import assess_article_noise, assess_signal_noise, signal_has_evidence
from .source_quality import classify_source


CATEGORIES = {
    "bank_product": "Банковский продукт",
    "payment": "Платёжный сервис",
    "ux": "UX-механика",
    "partnership": "Партнёрство",
    "regulation": "Регулирование",
    "market": "Рынок",
}

EVENT_KEYWORDS = {
    "launch": (
        "launch",
        "launched",
        "launches",
        "rolls out",
        "introduced",
        "introduces",
        "unveiled",
        "released",
        "добавил",
        "запустил",
        "запускает",
        "запустить",
        "представил",
        "выпустил",
        "выпускает",
        "обновил",
        "релиз",
        "поднял",
        "доступн",
    ),
    "partnership": (
        "partner",
        "partners",
        "partnership",
        "teams up",
        "collaboration",
        "сотруднич",
        "партнер",
        "партнёр",
        "партнерств",
        "партнёрств",
        "объединил",
        "совместн",
        "интегриров",
        "интеграц",
    ),
    "regulation": (
        "regulator",
        "regulation",
        "rules",
        "guidance",
        "law",
        "compliance",
        "consultation",
        "cbdc",
        "регулятор",
        "правила",
        "закон",
        "требован",
        "цб ",
        "банк россии",
        "минфин",
        "фнс",
        "обязал",
        "постановлен",
        "инструкц",
        "лицензи",
    ),
    "ux_change": (
        "experience",
        "flow",
        "interface",
        "redesign",
        "redesigned",
        "assistant",
        "personalization",
        "онбординг",
        "интерфейс",
        "сценарий",
        "пользовательск",
    ),
    "market_signal": (
        "report",
        "trend",
        "adoption",
        "survey",
        "growth",
        "исследование",
        "отчет",
        "отчёт",
        "тренд",
        "статистик",
    ),
}

PRODUCT_KEYWORDS = {
    "payments": (
        "payment",
        "payments",
        "checkout",
        "wallet",
        "card",
        "cards",
        "issuing",
        "merchant",
        "transfer",
        "tap to pay",
        "open banking payment",
        "acquiring",
        "interchange",
        "settlement",
        "remittance",
        "платеж",
        "платёж",
        "платежн",
        "кошелек",
        "кошелёк",
        "карта",
        "карты",
        "карту",
        "перевод",
        "переводы",
        "p2p",
        "сбп",
        "эквайринг",
        "эмисси",
        "инкассац",
        "рассрочк",
        "bnpl",
        "комисси",
        "тариф",
        "кэшбэк",
        "кешбэк",
    ),
    "banking": (
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
        "mortgage",
        "overdraft",
        "lending",
        "savings account",
        "банк",
        "банков",
        "счет",
        "счёт",
        "кредит",
        "кредитн",
        "ипотек",
        "вклад",
        "депозит",
        "займ",
        "заём",
        "заем",
        "овердрафт",
        "рефинансир",
        "микрокредит",
        "микрофинанс",
        "мфо",
        "лизинг",
        "брокер",
    ),
    "embedded_finance": (
        "embedded finance",
        "open banking",
        "banking-as-a-service",
        "baas",
        "api",
        "platform",
        "marketplace",
        "встроенн",
        "open banking",
        "цифровой рубль",
        "маркетплейс",
        "агрегатор",
    ),
    "identity": (
        "identity",
        "kyc",
        "verification",
        "digital id",
        "aml",
        "идентификац",
        "верификац",
        "ебс",
        "биометри",
        "снилс",
        "инн",
    ),
    "ux": (
        "app",
        "mobile",
        "assistant",
        "flow",
        "interface",
        "personalization",
        "experience",
        "приложение",
        "интерфейс",
        "клиентск",
    ),
    "insurance": (
        "insurance",
        "insurer",
        "underwriting",
        "policy",
        "страхов",
        "осаго",
        "каско",
        "полис",
    ),
    "investments": (
        "investment",
        "broker",
        "brokerage",
        "trading",
        "stocks",
        "etf",
        "fund",
        "инвестиц",
        "биржа",
        "торги",
        "пиф",
        "фондов",
        "акци",
        "облигац",
    ),
}

NOISE_KEYWORDS = (
    "conference",
    "webinar",
    "speaker",
    "agenda",
    "award",
    "awards",
    "appointed",
    "appointment",
    "hiring",
    "joins as",
    "podcast",
    "summit",
    "конференц",
    "вебинар",
    "спикер",
    "награда",
    "назначен",
    "ваканси",
)

FUNDING_KEYWORDS = ("funding", "investment", "raises", "raised", "series a", "seed round", "инвестиц", "раунд")

NEGATIVE_FACT_MARKERS = (
    "does not describe",
    "does not announce",
    "does not identify",
    "no specific product",
    "no concrete product",
    "without naming a customer scenario",
    "без конкретного",
    "не описывает",
    "не объявляет",
)

KNOWN_ACTORS = (
    "Visa",
    "Mastercard",
    "Stripe",
    "Revolut",
    "Wise",
    "PayPal",
    "Adyen",
    "Klarna",
    "Monzo",
    "Starling",
    "Nubank",
    "Apple",
    "Google",
    "Bank of England",
    "FCA",
    "ECB",
    "Federal Reserve",
)

BANNED_GENERIC = (
    "может быть важным",
    "стоит посмотреть",
    "рынок меняется",
    "возможный вывод",
)

FINTECH_ANCHOR_TERMS = (
    "bank", "payment", "card", "wallet", "loan", "credit", "mortgage",
    "deposit", "checkout", "merchant", "fintech", "finance", "transfer",
    "remittance", "regulator", "regulation", "compliance", "kyc",
    "open banking", "embedded finance", "baas", "bnpl", "cbdc",
    "investment", "insurance", "neobank", "lending",
    "банк", "платеж", "платёж", "карт", "кошел",
    "кредит", "ипотек", "вклад", "депозит", "займ", "заём", "заем",
    "счет", "счёт", "перевод", "сбп",
    "эквайринг", "эмисси", "инкассац",
    "финансов", "финтех",
    "регулятор", "цб ", "банк россии", "минфин", "фнс",
    "страхов", "инвестиц", "брокер", "биржа",
    "рассрочк", "bnpl", "кэшбэк", "кешбэк",
    "комисси", "тариф", "ставк",
    "криптовалют", "стейблкоин", "цифровой рубль",
    "необанк", "пенсион", "налог",
)


def rule_based_extract(article) -> dict:
    title = _compact(article.get("title", ""))
    url = article.get("url", "")
    text = _article_text(article)
    text_l = text.lower()
    signal_text = _compact(f"{title} {article.get('snippet', '')}")
    signal_text_l = signal_text.lower()
    quality = classify_source(url, article.get("source", ""), text)
    article_id = str(article.get("id") or _stable_id(url or title))
    event_type = _event_type(text_l)
    product_area = _product_area(text_l)
    category = _category(event_type, product_area, text_l)
    evidence = _evidence(text, url, event_type, product_area)
    actors = _actors(title, text, article.get("source", ""))
    geography = _geography(text, url)
    article_noise = assess_article_noise(article)

    decision = "keep"
    reject_reason = ""

    noise_hit = _first_hit(signal_text_l, NOISE_KEYWORDS) or _first_hit(text_l, NOISE_KEYWORDS)
    funding_hit = _first_hit(signal_text_l, FUNDING_KEYWORDS) or _first_hit(text_l, FUNDING_KEYWORDS)
    negative_marker = _first_hit(text_l, NEGATIVE_FACT_MARKERS)
    signal_event_type = _event_type(signal_text_l)
    signal_product_area = _product_area(signal_text_l)
    fintech_anchor_hits = _count_fintech_anchors(text_l)
    has_product_fact = bool(product_area and event_type in {"launch", "partnership", "ux_change", "regulation"})
    has_signal_surface_fact = bool(signal_product_area and signal_event_type in {"launch", "partnership", "ux_change", "regulation"})
    has_market_action = event_type == "market_signal" and product_area and _has_actionable_market_signal(text_l)

    if article_noise["is_noise"]:
        decision = "reject"
        reject_reason = article_noise["reason"]
        category = article_noise["category"]
    elif fintech_anchor_hits < 2:
        decision = "reject"
        reject_reason = f"weak fintech anchor: only {fintech_anchor_hits} core finance term(s) in body"
    elif noise_hit and not has_signal_surface_fact:
        decision = "reject"
        reject_reason = f"noise item: {noise_hit}"
    elif negative_marker:
        decision = "reject"
        reject_reason = f"explicitly says no concrete product fact: {negative_marker}"
    elif funding_hit and not has_product_fact:
        decision = "reject"
        reject_reason = "funding or investment without a concrete product scenario"
    elif event_type == "other" or not (has_product_fact or has_market_action):
        decision = "reject"
        reject_reason = "no concrete banking, payments, UX, partnership or regulation fact"
    elif not evidence:
        decision = "reject"
        reject_reason = "no evidence fragment supporting the signal"
    elif category == CATEGORIES["market"] and not has_market_action:
        decision = "reject"
        reject_reason = "generic market report without a concrete bank action"

    headline = _headline(title, event_type, product_area)
    summary_fact = _summary_fact(evidence, title)
    bank_relevance = _bank_relevance(event_type, product_area, actors, geography)
    confidence = _confidence(decision, evidence, quality, text)

    if decision == "reject":
        confidence = min(confidence, 0.4)

    return {
        "article_id": article_id,
        "title": title,
        "url": url,
        "source": article.get("source", "Unknown"),
        "published_at": article.get("date") or article.get("fetched_at") or "",
        "decision": decision,
        "reject_reason": reject_reason,
        "is_noise": decision == "reject",
        "rejection_reason": reject_reason if decision == "reject" else "",
        "canonical_event_key": _canonical_event_key(actors, event_type, product_area, geography, title),
        "headline": headline,
        "category": category,
        "event_type": event_type,
        "actors": actors,
        "product_area": product_area,
        "user_scenario": _user_scenario(text_l, product_area),
        "geography": geography,
        "summary_fact": summary_fact,
        "bank_relevance": bank_relevance,
        "evidence": evidence,
        "source_type": quality["source_type"],
        "is_primary_source": quality["is_primary_source"],
        "source_score": quality["source_score"],
        "source_quality_reason": quality["reason"],
        "confidence": round(confidence, 2),
    }


def llm_extract_signal(article) -> dict | None:
    article_json = json.dumps(
        {
            "id": article.get("id"),
            "title": article.get("title"),
            "source": article.get("source"),
            "url": article.get("url"),
            "date": article.get("date"),
            "snippet": article.get("snippet"),
            "full_text": _article_text(article)[:12000],
        },
        ensure_ascii=False,
    )
    system_prompt = (
        "Ты аналитик финтех-продуктов для внутренней команды банка. Твоя задача — не писать красивый текст, "
        "а извлекать проверяемый сигнал из публикации. Используй только факты из входной статьи. Если фактов "
        "недостаточно, верни decision=\"reject\". Нельзя выдумывать цифры, даты, участников, причины и выводы. "
        "ВАЖНО: текстовые поля summary_fact, bank_relevance и reject_reason всегда возвращай на русском языке, "
        "даже если исходная статья на английском — переводи смысл фактов, не выдумывая новые. "
        "Поля enum (event_type, product_area, source_type, geography, category) оставляй как есть. "
        "Верни только валидный JSON без markdown."
    )
    user_prompt = (
        "Проанализируй публикацию и верни CandidateSignal JSON.\n"
        "Критерии keep:\n"
        "- конкретный запуск продукта/фичи;\n"
        "- платёжная или банковская механика;\n"
        "- UX-механика;\n"
        "- партнёрство с понятным продуктовым эффектом;\n"
        "- регулирование;\n"
        "- рыночный сигнал с понятным действием для банка.\n\n"
        "Критерии reject:\n"
        "- конференции, спикеры, награды, вакансии;\n"
        "- назначения людей;\n"
        "- funding без продукта;\n"
        "- общий PR без фактов;\n"
        "- пересказ без нового факта;\n"
        "- нет связи с банковскими продуктами, платежами, UX или регулированием.\n\n"
        "Обязательные правила:\n"
        "- evidence должен содержать 1-3 коротких фрагмента из статьи, подтверждающих вывод.\n"
        "- why/bank_relevance должны быть конкретными, без фраз \"может быть важным\", \"стоит посмотреть\", \"рынок меняется\".\n"
        "- Если нет evidence, decision должен быть reject.\n\n"
        "Не присваивай importance/confidence сам. Эти числа считает backend по формуле.\n"
        "Заполняй только структурные поля и факторы:\n"
        "  category, event_type, actors, product_area, user_scenario, geography,\n"
        "  evidence (1-3 короткие точные цитаты из статьи), summary_fact, bank_relevance,\n"
        "  llm_factors: {\n"
        "    bank_relevance_signal: 0..1   # насколько крепкая связь с банком\n"
        "    signal_type_strength: 0..1    # насколько ярко выражен тип события\n"
        "    novelty_signal: 0..1          # это новое или перепечатка\n"
        "    user_impact_signal: 0..1      # значимо ли для клиентского сценария\n"
        "  }\n"
        "Backend сам пересчитает финальный importance (0-100) и confidence (0-1).\n\n"
        f"Входная статья:\n{article_json}"
    )
    result = complete_json(system_prompt, user_prompt, max_tokens=1200, temperature=0.1)
    if not isinstance(result, dict):
        return None
    return _normalize_llm_result(result, article)


def extract_signals(articles, use_llm=False, request_id="") -> list[dict]:
    signals = []
    llm_active = bool(use_llm and is_llm_available())
    log = AnalysisLogger(request_id=request_id or "pipeline") if request_id else None
    for article in articles:
        try:
            fallback = rule_based_extract(article)
        except Exception as exc:
            if log:
                log.error("EXTRACTION_FAILED", exc, step=3, article_url=article.get("url", ""))
            signals.append(_sanitize_signal(_fallback_rejected_signal(article, f"rule extraction failed: {exc}")))
            continue
        fallback["llm_used"] = False
        fallback["llm_fallback"] = False
        if not llm_active:
            signals.append(_sanitize_signal(fallback))
            continue

        try:
            llm_signal = llm_extract_signal(article)
        except Exception as exc:
            if log:
                log.error("LLM_REQUEST_FAILED", exc, step=3, article_url=article.get("url", ""))
            llm_signal = None
        if not llm_signal:
            # LLM was attempted but failed → mark for confidence penalty
            fallback["llm_used"] = True
            fallback["llm_fallback"] = True
            signals.append(_sanitize_signal(fallback))
            continue

        merged = {**fallback, **llm_signal}
        merged["llm_used"] = True
        merged["llm_fallback"] = False
        merged["article_id"] = fallback["article_id"]
        merged["url"] = fallback["url"]
        merged["source"] = fallback["source"]
        merged["source_type"] = fallback["source_type"]
        merged["source_score"] = fallback["source_score"]
        merged["is_primary_source"] = fallback["is_primary_source"]
        merged["source_quality_reason"] = fallback["source_quality_reason"]
        if not merged.get("evidence"):
            merged["decision"] = "reject"
            merged["reject_reason"] = "LLM returned no evidence"
        merged["canonical_event_key"] = _canonical_event_key(
            merged.get("actors") or fallback["actors"],
            merged.get("event_type") or fallback["event_type"],
            merged.get("product_area") or fallback["product_area"],
            merged.get("geography") or fallback["geography"],
            fallback["title"],
        )
        noise = assess_signal_noise(merged)
        if noise["is_noise"]:
            merged["decision"] = "reject"
            merged["reject_reason"] = noise["reason"]
            merged["rejection_reason"] = noise["reason"]
            merged["category"] = noise["category"]
        if merged.get("decision") == "keep" and not signal_has_evidence(merged):
            merged["decision"] = "reject"
            merged["reject_reason"] = "no evidence fragment supporting the signal"
            merged["rejection_reason"] = merged["reject_reason"]
        signals.append(_sanitize_signal(merged))
    return signals


def _fallback_rejected_signal(article, reason):
    title = _compact(article.get("title") or article.get("url") or "Untitled article")
    url = article.get("url", "")
    return {
        "article_id": str(article.get("id") or _stable_id(url or title)),
        "title": title,
        "headline": title,
        "url": url,
        "source": article.get("source", "Unknown"),
        "published_at": article.get("date") or article.get("fetched_at") or "",
        "decision": "reject",
        "reject_reason": reason,
        "rejection_reason": reason,
        "is_noise": True,
        "category": "Noise / irrelevant",
        "event_type": "other",
        "actors": [],
        "product_area": "",
        "user_scenario": "",
        "geography": "",
        "summary_fact": title,
        "bank_relevance": "",
        "evidence": [],
        "source_type": "unknown",
        "is_primary_source": False,
        "source_score": 30,
        "source_quality_reason": "fallback after extraction error",
        "confidence": 0.25,
        "llm_used": bool(is_llm_available()),
        "llm_fallback": True,
    }


def _normalize_llm_result(result, article) -> dict:
    fallback = rule_based_extract(article)
    text = _article_text(article)
    normalized = dict(result)
    normalized["decision"] = normalized.get("decision") if normalized.get("decision") in {"keep", "reject"} else "reject"
    normalized["category"] = normalized.get("category") if normalized.get("category") in set(CATEGORIES.values()) else fallback["category"]
    normalized["event_type"] = normalized.get("event_type") if normalized.get("event_type") in {
        "launch",
        "partnership",
        "regulation",
        "ux_change",
        "market_signal",
        "other",
    } else fallback["event_type"]
    normalized["evidence"] = _validated_evidence(normalized.get("evidence"), article.get("url", ""), text) or fallback["evidence"]
    normalized["actors"] = normalized.get("actors") if isinstance(normalized.get("actors"), list) else fallback["actors"]
    # We deliberately drop the LLM's own importance/confidence — backend
    # recomputes them deterministically. Keep llm_factors hint for diagnostics.
    if isinstance(normalized.get("llm_factors"), dict):
        normalized["llm_factors"] = {
            k: float(v) if isinstance(v, (int, float)) else None
            for k, v in normalized["llm_factors"].items()
        }
    normalized.pop("confidence", None)
    normalized.pop("importance", None)
    normalized.pop("hotness", None)
    return _sanitize_signal(normalized)


def _sanitize_signal(signal):
    for key in ("headline", "summary_fact", "bank_relevance", "reject_reason"):
        if isinstance(signal.get(key), str):
            signal[key] = _remove_banned(signal[key])
    if not isinstance(signal.get("evidence"), list):
        signal["evidence"] = []
    signal["is_noise"] = signal.get("decision") == "reject" or bool(signal.get("is_noise"))
    if signal["is_noise"] and not signal.get("rejection_reason"):
        signal["rejection_reason"] = signal.get("reject_reason", "")
    return signal


def _validated_evidence(raw_evidence, url, text):
    if not isinstance(raw_evidence, list):
        return []
    compact_text = _compact(text).lower()
    items = []
    for item in raw_evidence[:3]:
        quote = item.get("quote") if isinstance(item, dict) else str(item)
        quote = _compact(quote)
        if len(quote) < 12:
            continue
        if quote.lower()[:80] not in compact_text:
            continue
        items.append({"quote": quote[:280], "url": url})
    return items


def _article_text(article):
    return _compact(article.get("full_text") or article.get("markdown") or article.get("snippet") or "")


def _event_type(text_l):
    for event_type, keywords in EVENT_KEYWORDS.items():
        if _first_hit(text_l, keywords):
            return event_type
    return "other"


def _product_area(text_l):
    scores = {
        area: sum(1 for keyword in keywords if keyword in text_l)
        for area, keywords in PRODUCT_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else ""


def _category(event_type, product_area, text_l):
    if event_type == "regulation":
        return CATEGORIES["regulation"]
    if event_type == "partnership":
        return CATEGORIES["partnership"]
    if event_type == "ux_change" or product_area == "ux":
        return CATEGORIES["ux"]
    if product_area in {"payments", "embedded_finance"}:
        return CATEGORIES["payment"]
    if product_area in {"banking", "identity"}:
        return CATEGORIES["bank_product"]
    if event_type == "market_signal" or "market" in text_l:
        return CATEGORIES["market"]
    return CATEGORIES["market"]


def _evidence(text, url, event_type, product_area):
    sentences = _sentences(text)
    keywords = []
    keywords.extend(EVENT_KEYWORDS.get(event_type, ()))
    if product_area:
        keywords.extend(PRODUCT_KEYWORDS.get(product_area, ()))
    keywords.extend(("bank", "payment", "checkout", "wallet", "card", "regulation", "open banking"))

    matches = []
    for sentence in sentences:
        sentence_l = sentence.lower()
        if len(sentence) < 30:
            continue
        if any(keyword in sentence_l for keyword in keywords):
            matches.append({"quote": sentence[:280], "url": url})
        if len(matches) == 3:
            break
    return matches


def _sentences(text):
    compact = _compact(text)
    parts = re.split(r"(?<=[.!?])\s+", compact)
    if len(parts) == 1:
        parts = re.split(r"\s+[•-]\s+|\n+", compact)
    return [part.strip(" -") for part in parts if part.strip()]


def _actors(title, text, source):
    found = []
    blob = f"{title} {text[:800]}"
    for actor in KNOWN_ACTORS:
        if actor.lower() in blob.lower():
            found.append(actor)
    for match in re.findall(r"\b[A-Z][A-Za-z0-9&.-]{2,}(?:\s+[A-Z][A-Za-z0-9&.-]{2,})?\b", title):
        if match.lower() not in {"the", "new", "uk", "us"} and match not in found:
            found.append(match)
    if not found and source and source != "Unknown":
        found.append(source.split(".")[0].title())
    return found[:4]


def _geography(text, url):
    text_l = text.lower()
    geography_markers = (
        ("United Kingdom", ("uk", "britain", "fca", "bank of england", ".co.uk")),
        ("European Union", ("eu ", "european", "ecb", "europa.eu")),
        ("United States", ("us ", "u.s.", "united states", "federal reserve", ".gov")),
        ("Global", ("global", "worldwide", "international")),
    )
    host = urlsplit(url).netloc.lower() if url else ""
    for label, markers in geography_markers:
        if any(marker in text_l or marker in host for marker in markers):
            return label
    return "Global"


def _user_scenario(text_l, product_area):
    if "small business" in text_l or "sme" in text_l:
        return "финансовый и платежный workflow малого бизнеса"
    if "merchant" in text_l or "checkout" in text_l:
        return "checkout merchant-сценария и конверсия оплаты"
    if "cashback" in text_l or "debit" in text_l:
        return "вовлечение розничных клиентов в карточный продукт"
    if "open banking" in text_l:
        return "account-to-account платежи и consent-flow"
    if product_area == "ux":
        return "interaction в мобильном банковском приложении"
    return "банковский клиентский или merchant-сценарий"


def _summary_fact(evidence, title):
    if evidence:
        return _compact(evidence[0]["quote"])
    return title


def _bank_relevance(event_type, product_area, actors, geography):
    actor_text = ", ".join(actors[:2]) if actors else "competitor or provider"
    if event_type == "regulation":
        return f"Разложить изменение правил в {geography} на затронутые платежные, онбординговые и consent-flow."
    if event_type == "partnership":
        return f"Сравнить канал {actor_text} с партнерской дорожной картой банка и текущими embedded-finance интеграциями."
    if product_area == "payments":
        return "Проверить, меняет ли платежный flow конверсию checkout, использование wallet или экономику card issuing."
    if product_area == "banking":
        return "Сопоставить фичу с метриками engagement, card usage и удержания розничных клиентов."
    if product_area == "ux":
        return "Разобрать клиентский путь в приложении и проверить, сокращает ли такой interaction friction в приоритетных flow."
    return "Сформулировать один продуктовый эксперимент с владельцем, метрикой и затронутым клиентским сегментом."


def _has_actionable_market_signal(text_l):
    return any(
        keyword in text_l
        for keyword in (
            "bank",
            "payment",
            "checkout",
            "wallet",
            "open banking",
            "card",
            "merchant",
            "customers use",
            "adoption of",
        )
    )


def _headline(title, event_type, product_area):
    if title:
        return title
    return f"{event_type.replace('_', ' ')} in {product_area or 'fintech'}"


def _canonical_event_key(actors, event_type, product_area, geography, title):
    parts = [*(actors or [])[:3], event_type or "", product_area or "", geography or ""]
    raw = " ".join(part for part in parts if part).strip() or title
    normalized = re.sub(r"[^a-z0-9а-яё]+", " ", raw.lower(), flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


def _confidence(decision, evidence, quality, text):
    score = 0.35
    score += min(len(evidence), 3) * 0.12
    score += quality.get("source_score", 50) / 100 * 0.25
    if len(text) > 500:
        score += 0.08
    if quality.get("source_type") == "reprint":
        score -= 0.12
    if decision == "reject":
        score -= 0.15
    return max(0.0, min(0.95, score))


def _first_hit(text_l, keywords):
    return next((keyword for keyword in keywords if keyword in text_l), "")


def _count_fintech_anchors(text_l):
    hits = 0
    for term in FINTECH_ANCHOR_TERMS:
        if term in text_l:
            hits += 1
            if hits >= 3:
                return hits
    return hits


def _stable_id(value):
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _compact(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _remove_banned(text):
    cleaned = text
    for phrase in BANNED_GENERIC:
        cleaned = re.sub(re.escape(phrase), "проверьте конкретный продуктовый сценарий", cleaned, flags=re.IGNORECASE)
    return cleaned


def _clamp_float(value, fallback):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback
