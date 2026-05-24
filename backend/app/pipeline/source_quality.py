from urllib.parse import urlsplit


PRIMARY_DOMAIN_HINTS = {
    "mastercard.com",
    "visa.com",
    "stripe.com",
    "revolut.com",
    "wise.com",
    "paypal.com",
    "adyen.com",
    "checkout.com",
    "klarna.com",
    "monzo.com",
    "starlingbank.com",
    "nubank.com",
    "bankofengland.co.uk",
    "fca.org.uk",
    "ecb.europa.eu",
    "bis.org",
    "federalreserve.gov",
    "consumerfinance.gov",
    "gov.uk",
    "europa.eu",
}

PRIMARY_PATH_HINTS = (
    "newsroom",
    "press",
    "press-release",
    "blog",
    "news",
    "media",
    "regulation",
    "consultation",
    "policy",
)

TRUSTED_MEDIA_DOMAINS = {
    "finextra.com",
    "pymnts.com",
    "bankingdive.com",
    "techcrunch.com",
    "thefintechtimes.com",
    "openbankingexpo.com",
    "americanbanker.com",
    "fintechfutures.com",
    "bankautomationnews.com",
    "paymentsdive.com",
}

REPRINT_MARKERS = (
    "according to",
    "reported by",
    "via ",
    "citing ",
    "сообщает со ссылкой",
    "со ссылкой на",
    "перепечатка",
    "по данным издания",
)


def _host(url: str) -> str:
    try:
        return urlsplit(url or "").netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def _path(url: str) -> str:
    try:
        return urlsplit(url or "").path.lower()
    except ValueError:
        return ""


def _domain_matches(host: str, domains: set[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def classify_source(url, source, text) -> dict:
    host = _host(url)
    source_l = (source or "").lower()
    text_l = (text or "").lower()
    path = _path(url)

    reprint_marker = next((marker for marker in REPRINT_MARKERS if marker in text_l), "")

    if _domain_matches(host, PRIMARY_DOMAIN_HINTS) or any(name in source_l for name in ("newsroom", "central bank", "regulator")):
        is_primary_path = any(hint in path for hint in PRIMARY_PATH_HINTS) or _domain_matches(host, {
            "bankofengland.co.uk",
            "fca.org.uk",
            "ecb.europa.eu",
            "bis.org",
            "federalreserve.gov",
            "consumerfinance.gov",
            "gov.uk",
            "europa.eu",
        })
        if is_primary_path:
            return {
                "source_type": "primary",
                "source_score": 95,
                "is_primary_source": True,
                "reason": "official company, regulator or government source",
            }
        return {
            "source_type": "primary",
            "source_score": 88,
            "is_primary_source": True,
            "reason": "official domain",
        }

    if reprint_marker:
        return {
            "source_type": "reprint",
            "source_score": 45,
            "is_primary_source": False,
            "reason": f"reprint marker: {reprint_marker.strip()}",
        }

    if _domain_matches(host, TRUSTED_MEDIA_DOMAINS) or source_l in {d.split(".")[0] for d in TRUSTED_MEDIA_DOMAINS}:
        return {
            "source_type": "trusted_media",
            "source_score": 75,
            "is_primary_source": False,
            "reason": "recognized fintech or banking media",
        }

    return {
        "source_type": "unknown",
        "source_score": 55,
        "is_primary_source": False,
        "reason": "source is not in the trusted or primary lists",
    }
