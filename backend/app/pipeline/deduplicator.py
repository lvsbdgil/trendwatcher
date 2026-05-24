from difflib import SequenceMatcher


SOURCE_RANK = {
    "primary": 4,
    "trusted_media": 3,
    "unknown": 2,
    "reprint": 1,
}


def deduplicate_signals(candidates) -> tuple[list[dict], list[dict]]:
    groups = []
    duplicate_logs = []

    for candidate in candidates:
        if candidate.get("decision") != "keep":
            continue

        matched_group = _find_group(groups, candidate)
        if matched_group is None:
            groups.append(_new_group(candidate))
            continue

        reason = _merge_reason(matched_group, candidate)
        matched_group["items"].append(candidate)
        matched_group["sources"] = _unique_sources([*matched_group["sources"], _source_obj(candidate)])
        duplicate_logs.append(
            {
                "kept": matched_group["primary_source"].get("headline") or matched_group["primary_source"].get("title"),
                "merged": candidate.get("headline") or candidate.get("title"),
                "reason": reason,
                "canonical_event_key": matched_group.get("canonical_event_key", ""),
            }
        )
        _refresh_primary(matched_group)

    return [_finalize_group(group) for group in groups], duplicate_logs


def deduplicate_articles(articles):
    """Backward-compatible article dedup for older imports."""
    deduped = []
    logs = []
    for article in articles:
        matched = next((item for item in deduped if _similarity(item.get("title", ""), article.get("title", "")) >= 0.78), None)
        if not matched:
            deduped.append(article)
            continue
        logs.append({"kept": matched.get("title", ""), "removed": [article.get("title", "")], "reason": "similar title"})
    return deduped, logs


def _find_group(groups, candidate):
    for group in groups:
        same_key = candidate.get("canonical_event_key") and candidate.get("canonical_event_key") == group.get("canonical_event_key")
        same_fact_shape = any(_same_fact_shape(candidate, item) for item in group["items"])
        title_match = any(
            _similarity(candidate.get("title", ""), item.get("title", "")) >= 0.78
            or _similarity(candidate.get("headline", ""), item.get("headline", "")) >= 0.78
            for item in group["items"]
        )
        if same_key or same_fact_shape or title_match:
            return group
    return None


def _new_group(candidate):
    return {
        "canonical_event_key": candidate.get("canonical_event_key", ""),
        "items": [candidate],
        "primary_source": candidate,
        "sources": [_source_obj(candidate)],
    }


def _refresh_primary(group):
    group["primary_source"] = max(
        group["items"],
        key=lambda item: (
            SOURCE_RANK.get(item.get("source_type", "unknown"), 0),
            item.get("source_score", 0),
            item.get("confidence", 0),
        ),
    )


def _finalize_group(group):
    _refresh_primary(group)
    primary = dict(group["primary_source"])
    sources = _unique_sources(group["sources"])
    primary_url = group["primary_source"].get("url", "")
    canonical = group.get("canonical_event_key", "") or _fallback_cluster_id(group)
    primary["sources"] = sources
    primary["duplicate_group"] = {
        "canonical_event_key": canonical,
        "source_count": len(sources),
        "titles": [item.get("title", "") for item in group["items"]],
        "primary_url": primary_url,
    }
    primary["cross_source_count"] = len(sources)
    primary["supporting_evidence"] = _collect_evidence(group["items"])
    if primary.get("supporting_evidence") and not primary.get("evidence"):
        primary["evidence"] = primary["supporting_evidence"][:3]

    # Spec-required flat fields for the UI / callers
    primary["is_duplicate"] = False  # the group representative is not itself a dup
    primary["duplicate_cluster_id"] = canonical
    primary["primary_source_url"] = primary_url
    primary["duplicate_count"] = max(0, len(group["items"]) - 1)
    return primary


def _fallback_cluster_id(group):
    # Stable-ish hash from the first url/title — used when canonical key is empty.
    seed = (group["primary_source"].get("url") or group["primary_source"].get("title") or "").strip().lower()
    if not seed:
        return ""
    return "cluster_" + str(abs(hash(seed)) % 10_000_000)


def _source_obj(candidate):
    return {
        "url": candidate.get("url", ""),
        "title": candidate.get("title") or candidate.get("headline", ""),
        "source": candidate.get("source", "Unknown"),
        "kind": candidate.get("source_type", "unknown"),
    }


def _unique_sources(sources):
    seen = set()
    unique = []
    for source in sources:
        key = (source.get("url") or source.get("title", "")).lower().rstrip("/")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return sorted(unique, key=lambda item: SOURCE_RANK.get(item.get("kind", "unknown"), 0), reverse=True)


def _collect_evidence(items):
    seen = set()
    evidence = []
    for item in items:
        for quote in item.get("evidence", []):
            key = quote.get("quote", "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            evidence.append(quote)
    return evidence[:5]


def _merge_reason(group, candidate):
    if candidate.get("canonical_event_key") == group.get("canonical_event_key"):
        return "same canonical_event_key"
    if any(_same_fact_shape(candidate, item) for item in group["items"]):
        return "same actors, event_type and product_area"
    return "title/headline similarity >= 0.78"


def _similarity(left, right):
    return SequenceMatcher(None, (left or "").lower().strip(), (right or "").lower().strip()).ratio()


def _same_fact_shape(left, right):
    left_actors = {actor.lower() for actor in left.get("actors", [])}
    right_actors = {actor.lower() for actor in right.get("actors", [])}
    return (
        bool(left_actors & right_actors)
        and left.get("event_type") == right.get("event_type")
        and left.get("product_area") == right.get("product_area")
    )
