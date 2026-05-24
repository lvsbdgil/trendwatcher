import csv
from pathlib import Path

from backend.app.pipeline.relevance import assess_relevance
from backend.app.pipeline.runner import run_pipeline
from backend.app.adapters.openai import get_status as get_llm_status


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "sample_articles.csv"
BANNED = (
    "может быть важным",
    "стоит посмотреть",
    "рынок меняется",
    "возможный вывод",
    "требует дополнительной проверки",
)


def _no_llm_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def load_sample():
    with SAMPLE.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_pipeline_returns_signals_without_llm_key(monkeypatch):
    _no_llm_key(monkeypatch)

    result = run_pipeline(load_sample())

    assert result["stats"]["active_mode"] == "local_fallback"
    assert result["signals"]


def test_without_key_uses_local_fallback_and_does_not_call_llm(monkeypatch):
    _no_llm_key(monkeypatch)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("LLM must not be called without OPENAI_API_KEY")

    monkeypatch.setattr("backend.app.pipeline.signal_extractor.complete_json", fail_if_called)
    monkeypatch.setattr("backend.app.adapters.openai.requests.post", fail_if_called)

    result = run_pipeline(load_sample())

    assert result["stats"]["llm_enabled"] is False
    assert result["stats"]["active_mode"] == "local_fallback"
    assert result["signals"]


def test_selected_signals_have_required_card_fields(monkeypatch):
    _no_llm_key(monkeypatch)
    result = run_pipeline(load_sample())

    required = {
        "headline",
        "hotness",
        "category",
        "whyNow",
        "sources",
        "summary",
        "draft",
        "evidence",
        "confidence",
        "score_explanation",
    }
    for signal in result["signals"]:
        missing = [field for field in required if not signal.get(field)]
        assert not missing, f"missing fields in {signal.get('headline')}: {missing}"
        assert 0 <= signal["hotness"] <= 100


def test_noise_items_rejected_by_relevance_gate(monkeypatch):
    _no_llm_key(monkeypatch)
    cases = [
        {
            "title": "Fintech conference announces speaker lineup for autumn event",
            "snippet": "A fintech conference announced its speaker lineup, sponsors and agenda tracks.",
            "full_text": "A fintech conference announced its speaker lineup, sponsors and agenda tracks for an autumn event.",
        },
        {
            "title": "Payments startup appoints new chief marketing officer and wins award",
            "snippet": "A payments startup appointed a new chief marketing officer and received an industry award.",
            "full_text": "The award recognizes marketing activity rather than a banking customer scenario.",
        },
        {
            "title": "Fintech startup raises seed funding",
            "snippet": "The company raised funding but did not announce a product launch or bank partnership.",
            "full_text": "The company raised funding but did not announce a product launch, payment mechanism or regulation.",
        },
    ]

    verdicts = [assess_relevance(case) for case in cases]

    assert all(verdict["is_fintech"] is False for verdict in verdicts)


def test_duplicates_are_merged_and_generic_phrases_absent(monkeypatch):
    _no_llm_key(monkeypatch)
    result = run_pipeline(load_sample())

    assert result["duplicates"]
    combined_text = result["digest"].lower() + " " + " ".join(
        f"{signal['summary']} {signal['draft']} {signal.get('whyNow', '')}".lower()
        for signal in result["signals"]
    )
    for phrase in BANNED:
        assert phrase not in combined_text


def test_llm_status_reports_local_fallback_without_key(monkeypatch):
    _no_llm_key(monkeypatch)
    status = get_llm_status()

    assert status["provider"] == "openai"
    assert status["key_present"] is False
    assert status["llm_enabled"] is False
    assert status["active_mode"] == "local_fallback"
    assert status["model"]
