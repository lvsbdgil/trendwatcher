def _normalize(value):
    if value is None:
        return ""
    return str(value).strip()


def clean_articles(articles):
    cleaned = []
    seen_urls = set()

    for raw in articles:
        snippet = _normalize(raw.get("snippet"))
        full_text = _normalize(raw.get("full_text") or raw.get("text") or raw.get("content"))
        markdown = _normalize(raw.get("markdown"))
        body_text = full_text or markdown or snippet

        article = {
            "id": raw.get("id"),
            "title": _normalize(raw.get("title")),
            "source": _normalize(raw.get("source")) or "Unknown",
            "url": _normalize(raw.get("url")),
            "date": _normalize(raw.get("date")),
            "snippet": snippet or body_text[:1400],
            "full_text": body_text,
            "markdown": markdown,
            "fetched_at": _normalize(raw.get("fetched_at") or raw.get("fetchedAt")),
        }

        if not article["title"] or not article["url"] or not article["snippet"]:
            continue
        if len(article["title"]) < 8 or len(article["full_text"]) < 20:
            continue

        normalized_url = article["url"].lower().rstrip("/")
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        cleaned.append(article)

    return cleaned
