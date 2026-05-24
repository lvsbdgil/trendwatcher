from backend.app.pipeline.runner import run_pipeline


def _article(title, snippet, full_text="", source="Demo Source", url=None):
    return {
        "id": title.lower().replace(" ", "-")[:40],
        "title": title,
        "source": source,
        "url": url or f"https://example.com/{title.lower().replace(' ', '-')[:24]}",
        "date": "2026-05-10",
        "snippet": snippet,
        "full_text": full_text or snippet,
    }


def _demo_articles():
    return [
        _article(
            "Stripe launches biometric one-tap checkout for mobile merchants",
            "Stripe launched a biometric one-tap checkout flow for mobile merchants, combining saved cards, wallet tokens and risk checks inside a single payment step.",
            "Stripe launched a biometric one-tap checkout flow for mobile merchants. Merchants can turn it on from checkout settings in the United States and the United Kingdom.",
            source="Stripe Newsroom",
            url="https://stripe.com/newsroom/mobile-biometric-checkout",
        ),
        _article(
            "Visa and Shopify launch embedded working-capital wallet for SMEs",
            "Visa and Shopify launched an embedded wallet that lets eligible small businesses receive sales proceeds, pay suppliers and request working-capital offers.",
            "Visa and Shopify launched an embedded wallet for SMEs. Eligible merchants can receive card sales proceeds, pay suppliers with a virtual Visa credential and request working-capital offers from the Shopify admin.",
            source="Visa Newsroom",
            url="https://usa.visa.com/about-visa/newsroom/shopify-sme-wallet",
        ),
        _article(
            "UK FCA sets new consumer-consent rules for open banking payments",
            "The FCA published rules requiring clearer consent screens, payment status messages and revocation options for open banking payments.",
            "The FCA published new rules for open banking payments. Providers must show clearer consent screens, give users payment status messages and provide a simple revocation option for recurring account-to-account payments.",
            source="FCA",
            url="https://www.fca.org.uk/news/open-banking-payment-consent-rules",
        ),
        _article(
            "Fintech conference announces speaker lineup for autumn",
            "A fintech conference announced its speaker lineup, sponsors and agenda tracks for an autumn event.",
            "A fintech conference announced its speaker lineup, sponsors and agenda tracks for an autumn event. It does not describe a product launch, payment mechanism, bank partnership, UX change or regulation affecting banks.",
        ),
        _article(
            "Payments startup appoints new chief marketing officer and wins award",
            "A payments startup appointed a new chief marketing officer and received an industry award for brand awareness.",
            "A payments startup appointed a new chief marketing officer and received an industry award for brand awareness. It does not announce a product feature, payment flow, partnership with product impact or regulatory change.",
        ),
        _article(
            "Market report says digital finance adoption will keep growing",
            "A market report says digital finance adoption will keep growing, but gives no specific product launch, regulation or bank action.",
            "A market report says digital finance adoption will keep growing. The article uses broad phrases but does not identify a concrete product launch, payment mechanism, UX change, partnership with product impact or regulation.",
        ),
    ]


def test_noise_examples_are_rejected_and_not_signals(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_pipeline(_demo_articles(), use_llm=False, top_n=8)

    signal_titles = {signal["headline"] for signal in result["signals"]}
    rejected = {item["title"]: item for item in result["rejected_items"]}

    assert "Fintech conference announces speaker lineup for autumn" not in signal_titles
    assert rejected["Fintech conference announces speaker lineup for autumn"]["is_noise"] is True
    assert "Конференция/ивент" in rejected["Fintech conference announces speaker lineup for autumn"]["rejection_reason"]

    pr_item = rejected["Payments startup appoints new chief marketing officer and wins award"]
    assert pr_item["is_noise"] is True
    assert pr_item["category"] != "Партнёрство"
    assert pr_item["hotness"] <= 20
    assert "кадровое назначение/награда" in pr_item["rejection_reason"]


def test_generic_market_report_is_weak_without_concrete_evidence(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_pipeline(_demo_articles(), use_llm=False, top_n=8)
    rejected = {item["title"]: item for item in result["rejected_items"]}
    item = rejected["Market report says digital finance adoption will keep growing"]

    assert item["is_noise"] is True
    assert item["hotness"] <= 40
    assert item["confidence"] <= 0.55
    assert item["title"] not in result["digest"]


def test_selected_signals_are_complete_and_realistic(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_pipeline(_demo_articles(), use_llm=True, top_n=8)
    headlines = " ".join(signal["headline"] for signal in result["signals"])

    assert "Stripe launches biometric one-tap checkout" in headlines
    assert "Visa and Shopify launch embedded working-capital wallet" in headlines
    assert "UK FCA sets new consumer-consent rules" in headlines
    assert result["stats"]["active_mode"] == "local_fallback"

    for signal in result["signals"]:
        assert signal["is_noise"] is False
        assert isinstance(signal["hotness"], (int, float))
        assert 0 <= signal["hotness"] <= 100
        assert signal["hotness"] != 99
        assert signal["confidence"] <= 0.93
        assert signal["evidence"]
        assert signal["score_explanation"]
