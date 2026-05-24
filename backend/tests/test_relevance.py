import csv
import os
from pathlib import Path

import pytest

from backend.app.pipeline.relevance import assess_relevance, gate_mode


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "test_relevance.csv"


def _load_cases():
    cases = []
    with DATA_FILE.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cases.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "source": row["source"],
                    "url": row["url"],
                    "snippet": row["snippet"],
                    "full_text": row["snippet"],
                    "is_fintech": int(row["is_fintech"]) == 1,
                }
            )
    return cases


def _evaluate(verdicts):
    tp = sum(1 for case, v in verdicts if case["is_fintech"] and v["is_fintech"])
    fp = sum(1 for case, v in verdicts if not case["is_fintech"] and v["is_fintech"])
    fn = sum(1 for case, v in verdicts if case["is_fintech"] and not v["is_fintech"])
    tn = sum(1 for case, v in verdicts if not case["is_fintech"] and not v["is_fintech"])
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    accuracy = (tp + tn) / len(verdicts) if verdicts else 1.0
    return precision, recall, accuracy


def test_rule_based_gate_accuracy(monkeypatch):
    monkeypatch.setenv("RELEVANCE_GATE", "rule")
    cases = _load_cases()
    verdicts = [(case, assess_relevance(case)) for case in cases]
    precision, recall, accuracy = _evaluate(verdicts)

    misses = [
        (case["id"], case["title"], v["is_fintech"], v["reason"])
        for case, v in verdicts
        if v["is_fintech"] != case["is_fintech"]
    ]

    assert precision >= 0.85, f"precision too low: {precision:.2f}, misses={misses}"
    assert recall >= 0.85, f"recall too low: {recall:.2f}, misses={misses}"
    assert accuracy >= 0.85, f"accuracy too low: {accuracy:.2f}, misses={misses}"


def test_zero_anchor_short_circuit(monkeypatch):
    monkeypatch.setenv("RELEVANCE_GATE", "llm")
    verdict = assess_relevance(
        {
            "title": "Cats are great pets",
            "snippet": "Many people love cats because they are independent and clean animals.",
            "full_text": "Many people love cats because they are independent and clean animals.",
        }
    )
    assert verdict["is_fintech"] is False
    assert verdict["method"] == "rule_zero_anchor"


def test_off_mode_passes_everything(monkeypatch):
    monkeypatch.setenv("RELEVANCE_GATE", "off")
    verdict = assess_relevance({"title": "Random unrelated text", "snippet": "Nothing"})
    assert verdict["is_fintech"] is True
    assert verdict["method"] == "off"


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required for LLM gate test",
)
def test_llm_gate_accuracy(monkeypatch):
    monkeypatch.setenv("RELEVANCE_GATE", "llm")
    if gate_mode() != "llm":
        pytest.skip("LLM gate not active")
    cases = _load_cases()
    verdicts = [(case, assess_relevance(case)) for case in cases]
    precision, recall, accuracy = _evaluate(verdicts)
    misses = [
        (case["id"], case["title"], v["is_fintech"], v["reason"])
        for case, v in verdicts
        if v["is_fintech"] != case["is_fintech"]
    ]
    assert precision >= 0.92, f"LLM precision too low: {precision:.2f}, misses={misses}"
    assert recall >= 0.92, f"LLM recall too low: {recall:.2f}, misses={misses}"
