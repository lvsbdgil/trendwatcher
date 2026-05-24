import csv
from pathlib import Path

from backend.app.pipeline.runner import run_pipeline


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "sample_articles.csv"
BANNED = ("может быть важным", "стоит посмотреть", "рынок меняется", "возможный вывод")


def load_sample():
    with SAMPLE.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_conference_article_rejected():
    result = run_pipeline(load_sample(), use_llm=False)
    rejected_titles = {item["title"]: item for item in result["rejected_items"]}
    item = rejected_titles["Fintech conference announces speaker lineup for autumn event"]
    assert item["decision"] == "reject"
    assert "noise" in item["reject_reason"]


def test_duplicate_articles_merged():
    result = run_pipeline(load_sample(), use_llm=False)
    assert result["duplicates"]
    kept_before_dedup = result["stats"]["extracted_candidates"] - result["stats"]["rejected_count"]
    assert result["stats"]["after_deduplication"] < kept_before_dedup
    assert any("same" in log["reason"] for log in result["duplicates"])


def test_strong_product_launch_selected():
    result = run_pipeline(load_sample(), use_llm=False)
    headlines = " ".join(signal["headline"] for signal in result["signals"])
    assert "Stripe launches biometric one-tap checkout" in headlines
    assert "Visa and Shopify launch embedded working-capital wallet" in headlines


def test_every_selected_signal_has_evidence_and_sources():
    result = run_pipeline(load_sample(), use_llm=False)
    assert result["signals"]
    for signal in result["signals"]:
        assert signal["evidence"]
        assert signal["sources"]
        assert signal["confidence"] >= 0.45
        assert signal["score_explanation"]


def test_digest_has_no_banned_generic_phrases():
    result = run_pipeline(load_sample(), use_llm=False)
    digest = result["digest"].lower()
    for phrase in BANNED:
        assert phrase not in digest
