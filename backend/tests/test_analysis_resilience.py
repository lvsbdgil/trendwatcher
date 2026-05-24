import os

import pytest

from backend.app.pipeline.errors import AnalysisPipelineError
from backend.app.pipeline.normalizer import normalize_signal_card
from backend.app.pipeline.runner import run_pipeline
from backend.app.pipeline.scorer import score_signal
from backend.app.adapters import firecrawl
from backend.app.adapters._json import parse_llm_response as _parse_json


def _article(idx=1, title="Stripe launches biometric one-tap checkout"):
    text = (
        "Stripe launched a biometric payment checkout for merchants and bank card users. "
        "The product changes wallet, payment and checkout conversion flows for banks. "
        "Merchants can use the new payment feature in the United Kingdom."
    )
    return {
        "id": idx,
        "title": title,
        "source": "Stripe",
        "url": f"https://stripe.example/news/{idx}",
        "date": "2026-05-01",
        "snippet": text,
        "full_text": text,
    }


def test_firecrawl_search_mock_success(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test")
    monkeypatch.setattr(
        firecrawl,
        "_search_with_sdk",
        lambda *_args: [
            {
                "url": "https://example.com/a",
                "markdown": "# Bank launches payment wallet\nA bank launched a payment wallet for card users.",
                "metadata": {"title": "Bank launches payment wallet"},
            }
        ],
    )

    result = firecrawl.search_firecrawl("bank payment", limit=1)
    articles = firecrawl.firecrawl_items_to_articles(result["items"])

    assert len(articles) == 1
    assert articles[0]["url"] == "https://example.com/a"


def test_firecrawl_search_zero_links(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test")
    monkeypatch.setattr(firecrawl, "_search_with_sdk", lambda *_args: [])

    result = firecrawl.search_firecrawl("nothing", limit=5)

    assert result == {"items": [], "errors": []}


def test_scrape_urls_keeps_good_pages_when_one_fails(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test")

    def fake_scrape(url):
        if "bad" in url:
            raise firecrawl.FirecrawlFetchError("boom")
        return {
            "url": url,
            "title": "Good payment article",
            "markdown": "A bank launched a payment wallet for card users.",
            "text": "A bank launched a payment wallet for card users.",
        }

    monkeypatch.setattr(firecrawl, "scrape_url", fake_scrape)
    result = firecrawl.scrape_urls(["https://example.com/good", "https://example.com/bad"])

    assert len(result["items"]) == 1
    assert len(result["errors"]) == 1


def test_llm_markdown_json_is_parsed():
    parsed = _parse_json('```json\n{"decision":"keep","evidence":[{"quote":"abc"}]}\n```')

    assert parsed["decision"] == "keep"


def test_llm_invalid_json_returns_none():
    assert _parse_json("not json at all") is None


def test_scoring_v2_incomplete_data_is_normalized():
    scored = score_signal({"title": "Untitled", "decision": "keep"})
    card = normalize_signal_card(scored)

    assert isinstance(card["importance"], (int, float))
    assert isinstance(card["confidence"], (int, float))
    assert card["importance"] == card["importance"]
    assert card["confidence"] == card["confidence"]
    assert card["importance_breakdown"]
    assert card["confidence_breakdown"]


def test_pipeline_raises_no_valid_articles_for_empty_extraction(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(AnalysisPipelineError) as exc:
        run_pipeline([{"title": "", "url": "", "snippet": ""}], use_llm=False)

    assert exc.value.code == "NO_VALID_ARTICLES"


def test_pipeline_importance_confidence_are_finite(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = run_pipeline([_article()], use_llm=True)

    assert result["stats"]["active_mode"] == "local_fallback"
    for card in result["signals"]:
        assert card["importance"] == card["importance"]
        assert card["confidence"] == card["confidence"]
        assert card["scoring_version"] == "v2"
