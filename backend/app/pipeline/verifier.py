import logging
from concurrent.futures import ThreadPoolExecutor

from ..adapters.gemini import is_available as is_gemini_available
from ..adapters.openai import is_available as is_llm_available
from .llm_enricher import critique_as_devil_advocate, critique_with_gemini


logger = logging.getLogger(__name__)

_VALID_GRADES = {"high", "medium", "low", "noise"}


def cross_critique_parallel(signals: list[dict]) -> list[dict]:
    """
    Runs two parallel critique streams:
      Stream A — Gemini critiques each OpenAI signal
      Stream B — OpenAI plays devil's advocate on its own signals
    Then merges into consensus_status + adjusted hotness.
    Fully fault-tolerant: returns signals unchanged if both LLMs unavailable.
    """
    openai_ok = is_llm_available()
    gemini_ok = is_gemini_available()

    if not openai_ok and not gemini_ok:
        return [_stamp_no_llm(s) for s in signals]

    gemini_results = [None] * len(signals)
    openai_results = [None] * len(signals)

    tasks = []
    with ThreadPoolExecutor(max_workers=min(8, len(signals) * 2)) as executor:
        if gemini_ok:
            for i, sig in enumerate(signals):
                tasks.append(("gemini", i, executor.submit(_safe_gemini, sig)))
        if openai_ok:
            for i, sig in enumerate(signals):
                tasks.append(("openai", i, executor.submit(_safe_openai, sig)))

        for stream, idx, future in tasks:
            try:
                result = future.result(timeout=35)
            except Exception as exc:
                logger.warning("cross_critique %s[%d] timed out: %s", stream, idx, exc)
                result = None
            if stream == "gemini":
                gemini_results[idx] = result
            else:
                openai_results[idx] = result

    return _merge(signals, gemini_results, openai_results)


def _safe_gemini(signal: dict) -> dict | None:
    try:
        return critique_with_gemini(signal)
    except Exception as exc:
        logger.warning("Gemini critique failed: %s", exc)
        return None


def _safe_openai(signal: dict) -> dict | None:
    try:
        return critique_as_devil_advocate(signal)
    except Exception as exc:
        logger.warning("OpenAI devil-advocate failed: %s", exc)
        return None


def _merge(signals: list[dict], gemini_results: list, openai_results: list) -> list[dict]:
    merged = []
    for i, signal in enumerate(signals):
        g = gemini_results[i]
        o = openai_results[i]
        merged.append(_apply_consensus(signal, g, o))
    return merged


def _apply_consensus(signal: dict, gemini: dict | None, openai: dict | None) -> dict:
    updated = dict(signal)

    g_grade = _safe_grade(gemini, "gemini_grade")
    o_grade = _safe_grade(openai, "openai_review_grade")
    g_delta = _safe_delta(gemini, "gemini_hotness_delta")
    o_delta = _safe_delta(openai, "openai_review_delta")

    updated["gemini_grade"] = g_grade
    updated["gemini_note"] = (gemini or {}).get("gemini_note") or None
    updated["openai_review_grade"] = o_grade
    updated["openai_review_note"] = (openai or {}).get("openai_review_note") or None

    current_hotness = int(updated.get("hotness") or 0)
    total_delta = g_delta + o_delta
    updated["hotness"] = max(0, min(100, current_hotness + total_delta))

    updated["consensus_status"] = _consensus_status(g_grade, o_grade)
    return updated


def _consensus_status(g_grade: str | None, o_grade: str | None) -> str:
    if g_grade is None and o_grade is None:
        return "no_llm"
    if g_grade is None or o_grade is None:
        return "single_llm"

    both_weak = g_grade in ("low", "noise") and o_grade in ("low", "noise")
    both_strong = g_grade in ("high", "medium") and o_grade in ("high", "medium")

    if both_strong:
        return "both_agree"
    if both_weak:
        return "both_reject"
    if o_grade in ("high", "medium"):
        return "openai_holds"
    return "gemini_flags"


def _safe_grade(result: dict | None, key: str) -> str | None:
    if not isinstance(result, dict):
        return None
    grade = str(result.get(key) or "").strip().lower()
    return grade if grade in _VALID_GRADES else None


def _safe_delta(result: dict | None, key: str) -> int:
    if not isinstance(result, dict):
        return 0
    try:
        return max(-20, min(10, int(result.get(key, 0))))
    except (TypeError, ValueError):
        return 0


def _stamp_no_llm(signal: dict) -> dict:
    return {
        **signal,
        "consensus_status": "no_llm",
        "gemini_grade": None,
        "gemini_note": None,
        "openai_review_grade": None,
        "openai_review_note": None,
    }
