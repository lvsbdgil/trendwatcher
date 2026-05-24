"""LLM-based signal enrichment: card improvement and cross-critique prompts."""
from __future__ import annotations

import json
import re

from ..adapters import gemini as gemini_adapter
from ..adapters import openai as openai_adapter


TEXT_FIELDS = ("headline", "summary", "why_now", "whyNow", "draft")
IMMUTABLE_FIELDS = ("hotness", "sources", "category", "evidence", "score_explanation", "confidence")
BANNED_GENERIC = (
    "может быть важным",
    "стоит посмотреть",
    "рынок меняется",
    "требует дополнительной проверки",
    "возможный вывод",
    "проверить, применим ли",
)

_PROJECT_CONTEXT = """
Ты работаешь в системе TrendWatcher — инструменте мониторинга финтех-публикаций
для продуктовой команды российского банка.

Задача команды: отслеживать значимые события в финтех-индустрии (запуски продуктов,
регуляторные изменения, партнёрства с продуктовым результатом, изменения платёжной
инфраструктуры), чтобы принимать обоснованные продуктовые решения.

Команда следит за конкурентами (Тинькофф, СберБанк, ВТБ, Яндекс Пей, Stripe,
Visa, Mastercard), регуляторами (ЦБ РФ, ФНС, Минфин) и мировым рынком (BNPL,
открытый банкинг, цифровые валюты, биометрия, токенизация).

ВАЖЕН сигнал, если он:
• описывает конкретный запуск продукта/фичи с проверяемыми данными
• меняет регуляторные требования с прямым влиянием на банковский продукт
• фиксирует партнёрство с конкретным продуктовым результатом (не просто MOU)
• меняет пользовательский сценарий или платёжный флоу
НЕ ВАЖЕН (шум): конференции, кадровые назначения, награды, PR без продукта,
общая аналитика без конкретного факта, финансирование без продуктового события.
"""

_GRADE_SCALE = """
grade шкала:
  high   — конкретное событие с прямым и проверяемым влиянием на банковский продукт
            или клиентский сценарий; есть конкретные данные (цифры, компании, даты)
  medium — важное событие, но влияние косвенное или данные неполные
  low    — слабые данные, общие слова, нет конкретного сценария для банка
  noise  — шум: конференция, кадровое назначение, награда, funding без продукта,
            PR без конкретики
"""

_IMPROVE_CARD_SYSTEM = (
    "Ты редактор внутреннего финтех-дайджеста банка. Улучши только формулировки карточки. "
    "Используй только facts/evidence из входной карточки. Не меняй hotness, sources, category, evidence, "
    "score_explanation и confidence. ВСЕ выходные текстовые поля (summary, why_now, whyNow, draft) "
    "ВСЕГДА на русском языке — даже если исходная статья на английском, переведи смысл фактов на русский, "
    "не выдумывая новые. Поле headline можно оставить на языке оригинала, если оно уже задано как заголовок. "
    "Верни только валидный JSON."
)

_IMPROVE_CARD_USER = (
    "Верни JSON с ключами headline, summary, why_now, whyNow, draft. "
    "summary, why_now, whyNow и draft строго на русском языке. "
    "Текст должен быть конкретным для продуктовой/конкурентной команды банка. "
    "Запрещены фразы: может быть важным, стоит посмотреть, рынок меняется, требует дополнительной проверки, возможный вывод. "
    "Если факта нет в evidence или исходной карточке, не добавляй его.\n\n"
    "Входная карточка:\n{card_json}"
)

_DEVIL_ADVOCATE_SYSTEM = f"""{_PROJECT_CONTEXT}

Твоя роль: АДВОКАТ ДЬЯВОЛА.

Ты уже выдал этот сигнал как потенциально важный. Теперь сыграй роль скептика —
найди причины НЕ включать его в финальный дайджест.

Задай себе вопросы:
1. Есть ли конкретные факты или только общие слова?
2. Есть ли прямой сценарий применения для банка, или связь косвенная?
3. Это реальное событие (запуск, изменение, решение) или просто слух/прогноз?
4. Подтверждает ли evidence заголовок, или это clickbait?
5. Это действительно ново, или уже было 6 месяцев назад?

grade шкала:
  high   — прошёл все проверки, конкретный факт, прямой банковский сценарий
  medium — есть сомнения, но сигнал достаточно конкретен
  low    — слабые данные, косвенная связь, нет чёткого сценария
  noise  — шум, не стоит включать

openai_review_delta: от -20 до +10
  Отрицательный если нашёл серьёзные слабые места.
  Положительный только если evidence неожиданно сильные.

Верни строго валидный JSON без markdown:
{{"openai_review_grade": "...", "openai_review_note": "1-2 предложения", "openai_review_delta": 0}}
"""

_DEVIL_ADVOCATE_USER = """Твой сигнал для критической проверки:

Заголовок: {headline}
Категория: {category}
Текущая важность: {hotness}/100
Краткое описание: {summary}
Почему важно: {why_now}
Черновик для команды: {draft}
Подтверждения (evidence):
{evidence_text}

Сыграй роль скептика и верни JSON.
"""

_GEMINI_CRITIQUE_SYSTEM = f"""{_PROJECT_CONTEXT}

Твоя роль: НЕЗАВИСИМЫЙ РЕЦЕНЗЕНТ сигналов.

OpenAI уже извлёк и оценил сигнал из публикации. Твоя задача — независимо проверить
этот сигнал и дать объективную оценку. Ты не знаешь, насколько OpenAI уверен —
оценивай только по содержанию сигнала.

{_GRADE_SCALE}

hotness_delta: от -20 до +10
  +5..+10 — evidence конкретные, факты проверяемы, прямой банковский сценарий
  0       — нейтрально, согласен с текущей оценкой
  -5..-10 — слабые данные или косвенная связь
  -15..-20 — шум или нет реального события

Верни строго валидный JSON без markdown:
{{"gemini_grade": "...", "gemini_note": "1-2 предложения", "gemini_hotness_delta": 0}}
"""

_GEMINI_CRITIQUE_USER = """Сигнал для проверки:

Заголовок: {headline}
Категория: {category}
Важность (OpenAI): {hotness}/100
Краткое описание: {summary}
Почему важно сейчас: {why_now}
Подтверждения (evidence):
{evidence_text}

Оцени этот сигнал независимо и верни JSON.
"""


def improve_card(card: dict) -> dict | None:
    if not card.get("evidence"):
        return None

    improved = openai_adapter.complete_json(
        _IMPROVE_CARD_SYSTEM,
        _IMPROVE_CARD_USER.format(card_json=json.dumps(card, ensure_ascii=False)),
        max_tokens=700,
        temperature=0.1,
    )
    if not isinstance(improved, dict):
        return None

    candidate = dict(card)
    for field in TEXT_FIELDS:
        if isinstance(improved.get(field), str) and improved[field].strip():
            candidate[field] = _sanitize_text(improved[field])
    candidate["whyNow"] = candidate.get("why_now") or candidate.get("whyNow", "")

    if not _immutable_fields_intact(card, candidate):
        return None
    if _contains_hallucinations(card, candidate):
        return None
    return candidate


def critique_as_devil_advocate(signal: dict) -> dict | None:
    """OpenAI plays devil's advocate on its own signal."""
    user_prompt = _DEVIL_ADVOCATE_USER.format(
        headline=signal.get("headline") or signal.get("title", ""),
        category=signal.get("category", "—"),
        hotness=signal.get("hotness", 0),
        summary=signal.get("summary", "—"),
        why_now=signal.get("whyNow") or signal.get("why_now", "—"),
        draft=signal.get("draft", "—"),
        evidence_text=_format_evidence(signal),
    )
    result = openai_adapter.complete_json(
        _DEVIL_ADVOCATE_SYSTEM, user_prompt, max_tokens=300, temperature=0.15
    )
    return result if isinstance(result, dict) else None


def critique_with_gemini(signal: dict) -> dict | None:
    """Gemini independently reviews an OpenAI-extracted signal."""
    user_prompt = _GEMINI_CRITIQUE_USER.format(
        headline=signal.get("headline") or signal.get("title", ""),
        category=signal.get("category", "—"),
        hotness=signal.get("hotness", 0),
        summary=signal.get("summary", "—"),
        why_now=signal.get("whyNow") or signal.get("why_now", "—"),
        evidence_text=_format_evidence(signal),
    )
    return gemini_adapter.complete_json(
        _GEMINI_CRITIQUE_SYSTEM, user_prompt, max_tokens=300
    )


def _format_evidence(signal: dict) -> str:
    evidence = signal.get("evidence") or []
    lines = "\n".join(
        f"  • {e if isinstance(e, str) else e.get('quote', '')}"
        for e in evidence[:3]
    )
    return lines or "  (нет)"


def _sanitize_text(text: str) -> str:
    cleaned = str(text or "").strip()
    replacements = {
        "может быть важным": "даёт продуктовой команде конкретный сценарий для проверки",
        "стоит посмотреть": "сравните этот сценарий с текущей дорожной картой",
        "рынок меняется": "клиентский сценарий получил новый проверяемый пример",
        "требует дополнительной проверки": "проверьте указанный источник и влияние на свой сценарий",
        "возможный вывод": "следующий шаг",
        "проверить, применим ли": "сравнить с",
    }
    for phrase, replacement in replacements.items():
        cleaned = re.sub(re.escape(phrase), replacement, cleaned, flags=re.IGNORECASE)
    return cleaned


def _immutable_fields_intact(original: dict, candidate: dict) -> bool:
    return all(candidate.get(f) == original.get(f) for f in IMMUTABLE_FIELDS)


def _contains_hallucinations(original: dict, candidate: dict) -> bool:
    allowed_text = json.dumps(
        {f: original.get(f) for f in ("headline", "summary", "why_now", "draft", "evidence", "sources")},
        ensure_ascii=False,
    ).lower()

    for field in TEXT_FIELDS:
        text = str(candidate.get(field, ""))
        if any(phrase in text.lower() for phrase in BANNED_GENERIC):
            return True
        for number in re.findall(r"\d+(?:[.,]\d+)?%?", text):
            if number.lower() not in allowed_text:
                return True
        for url in re.findall(r"https?://\S+", text):
            if url.lower().rstrip(".,)") not in allowed_text:
                return True
    return False
