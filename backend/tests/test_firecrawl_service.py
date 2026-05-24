"""Unit tests for the Firecrawl wrapper: normalizer and error mapping."""
from __future__ import annotations

import pytest

from backend.app.adapters import firecrawl as fc


def test_normalize_accepts_data_list():
    raw = {"data": [
        {"url": "https://a", "title": "T1", "description": "S1"},
        {"link": "https://b", "name": "T2"},
    ]}
    out = fc.normalize_firecrawl_results(raw)
    assert [item["url"] for item in out] == ["https://a", "https://b"]
    assert out[0]["snippet"] == "S1"
    assert out[1]["title"] == "T2"


def test_normalize_accepts_v2_web_news_buckets():
    raw = {"data": {
        "web": [{"url": "https://web/1", "title": "Web"}],
        "news": [{"url": "https://news/1", "title": "News"}],
    }}
    out = fc.normalize_firecrawl_results(raw)
    assert {item["url"] for item in out} == {"https://web/1", "https://news/1"}


def test_normalize_accepts_string_list():
    raw = ["https://a", "https://b", ""]
    out = fc.normalize_firecrawl_results(raw)
    assert [item["url"] for item in out] == ["https://a", "https://b"]
    assert all(item["title"] is None for item in out)


def test_normalize_handles_pydantic_like_objects():
    class FakeResult:
        def model_dump(self):
            return {"results": [{"sourceUrl": "https://x", "summary": "snip"}]}

    out = fc.normalize_firecrawl_results(FakeResult())
    assert out == [{"url": "https://x", "title": None, "source": None, "snippet": "snip"}]


def test_normalize_returns_empty_for_garbage():
    assert fc.normalize_firecrawl_results(None) == []
    assert fc.normalize_firecrawl_results({}) == []
    assert fc.normalize_firecrawl_results(42) == []


@pytest.mark.parametrize("status,expected", [
    (401, fc.FirecrawlAuthError),
    (403, fc.FirecrawlAuthError),
    (429, fc.FirecrawlRateLimitError),
    (502, fc.FirecrawlFetchError),
    (None, fc.FirecrawlFetchError),
])
def test_wrap_sdk_error_picks_correct_subclass(status, expected):
    exc = Exception("sdk boom")
    if status is not None:
        exc.status_code = status
    wrapped = fc._wrap_sdk_error(exc, "fallback msg")
    assert isinstance(wrapped, expected)
    assert "sdk boom" in str(wrapped) or "fallback msg" in str(wrapped)
    if status is not None:
        assert wrapped.status == status


def test_wrap_sdk_error_extracts_status_from_message():
    exc = Exception("Got 429 too many requests")
    wrapped = fc._wrap_sdk_error(exc, "fallback")
    assert isinstance(wrapped, fc.FirecrawlRateLimitError)
    assert wrapped.status == 429
