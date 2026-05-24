from ..adapters.gemini import is_available as is_gemini_available
from ..adapters.openai import get_settings as get_llm_settings, is_available as is_llm_available
from .llm_enricher import improve_card
from .cards import make_rule_based_card
from .cleaner import clean_articles
from .recency_filter import filter_by_recency
from .deduplicator import deduplicate_signals
from .digest import build_digest
from .errors import AnalysisPipelineError
from .logging import AnalysisLogger, new_request_id
from .noise_filter import SIGNAL_THRESHOLD, normalize_rejected_item
from .normalizer import normalize_result, normalize_signal_card
from .relevance import filter_by_relevance
from .scorer import score_signal, score_signals
from .signal_extractor import extract_signals
from .verifier import cross_critique_parallel


def run_pipeline(
    articles,
    top_n=5,
    use_llm=True,
    *,
    request_id=None,
    query="",
    limit=None,
    user_id=None,
):
    request_id = request_id or new_request_id()
    log = AnalysisLogger(request_id=request_id, query=query, limit=limit, user_id=user_id)
    articles = articles or []
    llm_settings = get_llm_settings()
    llm_active = bool(use_llm and llm_settings.get("api_key"))
    log.info(
        "analysis_started",
        selected_limit=top_n,
        article_count=len(articles),
        llm_enabled=llm_active,
    )

    current_step_num = 2
    current_step_name = "extract_articles"
    try:
        # Step 2: turn raw rows into article objects with body text.
        current_step_num, current_step_name = 2, "extract_articles"
        log.step_started(current_step_num, current_step_name, input_count=len(articles))
        cleaned = clean_articles(articles)
        failed = max(0, len(articles) - len(cleaned))
        log.step_completed(current_step_num, current_step_name, success=len(cleaned), failed=failed)
        if not cleaned:
            raise AnalysisPipelineError(
                "NO_VALID_ARTICLES",
                "No valid articles remained after extraction.",
                step=current_step_num,
                step_name=current_step_name,
                request_id=request_id,
            )

        # Step 2a: recency filter — keep only articles published within the last
        # 12 months. Older articles and items without a confirmed publication
        # date go to the rejected bucket with a Russian reason.
        current_step_num, current_step_name = 2, "filter_recency"
        log.step_started(current_step_num, current_step_name, documents=len(cleaned))
        fresh, too_old, no_date = filter_by_recency(cleaned)
        log.step_completed(
            current_step_num, current_step_name,
            count=len(fresh), too_old=len(too_old), no_date=len(no_date),
        )

        # Step 2b: noise / relevance filter.
        current_step_num, current_step_name = 2, "filter_noise"
        log.step_started(current_step_num, current_step_name, documents=len(fresh))
        relevant, irrelevant = filter_by_relevance(fresh)
        log.step_completed(current_step_num, current_step_name, count=len(relevant), rejected=len(irrelevant))
        # Merge too-old / no-date items into the irrelevant bucket so they
        # show up in "Материалы, отброшенные как шум" with the correct reason.
        irrelevant = [*irrelevant, *too_old, *no_date]
        if not relevant:
            raise AnalysisPipelineError(
                "NO_VALID_ARTICLES",
                "All extracted articles were filtered out as irrelevant or noise.",
                step=current_step_num,
                step_name=current_step_name,
                request_id=request_id,
            )

        # Step 3: LLM (or rule-based) signal extraction.
        current_step_num, current_step_name = 3, "llm_analysis"
        log.step_started(
            current_step_num,
            current_step_name,
            documents=len(relevant),
            llm_enabled=llm_active,
        )
        candidates = extract_signals(relevant, use_llm=llm_active, request_id=request_id)
        extractor_rejected = [c for c in candidates if c.get("decision") == "reject"]
        kept_candidates = [c for c in candidates if c.get("decision") == "keep"]
        log.step_completed(
            current_step_num,
            current_step_name,
            count=len(candidates),
            kept=len(kept_candidates),
            rejected=len(extractor_rejected),
        )

        # Step 3b: deduplication.
        current_step_num, current_step_name = 3, "deduplicate"
        log.step_started(current_step_num, current_step_name, candidates=len(kept_candidates))
        rejected_items = [
            score_signal(normalize_rejected_item(item))
            for item in [*irrelevant, *extractor_rejected]
        ]
        deduped_signals, duplicate_logs = deduplicate_signals(kept_candidates)
        log.step_completed(
            current_step_num,
            current_step_name,
            count=len(deduped_signals),
            duplicates=len(duplicate_logs),
        )

        # Step 4: scoring v2.
        current_step_num, current_step_name = 4, "scoring"
        log.step_started(current_step_num, current_step_name, signals=len(deduped_signals))
        scored_signals, selected = score_signals(deduped_signals, top_n=top_n)
        log.step_completed(current_step_num, current_step_name, count=len(selected))
    except AnalysisPipelineError:
        raise
    except Exception as exc:
        log.error("SCORING_FAILED", exc, step=current_step_num, step_name=current_step_name)
        raise AnalysisPipelineError(
            "SCORING_FAILED",
            f"{type(exc).__name__}: {exc}",
            step=current_step_num,
            step_name=current_step_name,
            request_id=request_id,
        ) from exc

    # Step 5: rule-based card build + optional LLM polish.
    current_step_num, current_step_name = 5, "build_cards"
    log.step_started(current_step_num, current_step_name, selected=len(selected))
    cards = [normalize_signal_card(make_rule_based_card(signal), idx) for idx, signal in enumerate(selected)]
    if llm_active:
        improved_cards = []
        for idx, card in enumerate(cards):
            try:
                improved_cards.append(normalize_signal_card(improve_card(card) or card, idx))
            except Exception as exc:
                log.error("LLM_REQUEST_FAILED", exc, step=5, step_name=current_step_name, card_id=card.get("id"))
                degraded = dict(card)
                degraded["llm_fallback"] = True
                degraded["confidence"] = min(float(degraded.get("confidence") or 0.55), 0.55)
                degraded["confidence_reason"] = (
                    (degraded.get("confidence_reason") or "")
                    + " LLM unavailable; card uses rule-based fallback."
                ).strip()
                improved_cards.append(normalize_signal_card(degraded, idx))
        cards = improved_cards
    log.step_completed(current_step_num, current_step_name, count=len(cards))

    gemini_active = is_gemini_available()

    # Cross-critique: both streams run in parallel, then merge consensus
    if llm_active or gemini_active:
        cards = cross_critique_parallel(cards)

    # Both LLMs agreed this signal is noise → move to rejected
    consensus_rejected = [c for c in cards if c.get("consensus_status") == "both_reject"]
    cards = [c for c in cards if c.get("consensus_status") != "both_reject"]
    rejected_items.extend(
        score_signal(normalize_rejected_item({**c, "reject_reason": "both_llm_reject: " + (c.get("gemini_note") or "")}))
        for c in consensus_rejected
    )

    stats = {
        "input_count": len(articles),
        "after_cleaning": len(cleaned),
        "after_relevance_gate": len(relevant),
        "not_fintech_count": len(irrelevant),
        "extracted_candidates": len(candidates),
        "rejected_count": len(extractor_rejected),
        "total_rejected_count": len(rejected_items),
        "after_deduplication": len(deduped_signals),
        "selected_signals": len(cards),
        "signal_threshold": SIGNAL_THRESHOLD,
        "llm_enabled": llm_active,
        "active_mode": llm_settings.get("provider", "llm") if llm_active else "local_fallback",
        "degraded_mode": not llm_active,
        "request_id": request_id,
        "gemini_active": gemini_active,
        "consensus_both_agree": sum(1 for c in cards if c.get("consensus_status") == "both_agree"),
        "consensus_both_reject": len(consensus_rejected),
        "consensus_openai_holds": sum(1 for c in cards if c.get("consensus_status") == "openai_holds"),
        "consensus_gemini_flags": sum(1 for c in cards if c.get("consensus_status") == "gemini_flags"),
        "noise_breakdown": _noise_breakdown(rejected_items, duplicate_logs),
    }
    log.step_started(6, "build_digest", signal_cards=len(cards))
    digest = build_digest(cards, stats=stats, duplicate_logs=duplicate_logs)
    log.step_completed(6, "build_digest")

    result = normalize_result({
        "stats": stats,
        "duplicates": duplicate_logs,
        "rejected_items": rejected_items,
        "scored_articles": [*scored_signals, *rejected_items],
        "signals": cards,
        "digest": digest,
    })
    # Canonical end-of-pipeline marker requested by debug spec.
    log.step_completed(6, "response", cards=len(result["signals"]))
    log.info(
        "analysis_completed",
        signal_cards=len(result["signals"]),
        final_response_schema=result.get("response_schema"),
    )
    return result


def _noise_breakdown(rejected_items, duplicate_logs):
    breakdown = {
        "not_fintech": 0,
        "conference_event": 0,
        "duplicates_reprints": len(duplicate_logs),
        "irrelevant": 0,
        "no_evidence": 0,
        "funding_without_product": 0,
        "other": 0,
    }
    for item in rejected_items:
        reason = (item.get("reject_reason") or "").lower()
        if any(marker in reason for marker in ("conference", "event", "webinar", "speaker", "award", "назнач", "кадров", "chief marketing")):
            breakdown["conference_event"] += 1
        elif "evidence" in reason:
            breakdown["no_evidence"] += 1
        elif "funding" in reason or "investment" in reason:
            breakdown["funding_without_product"] += 1
        elif "no concrete" in reason or "generic" in reason:
            breakdown["irrelevant"] += 1
        elif "not fintech" in reason:
            breakdown["not_fintech"] += 1
        else:
            breakdown["other"] += 1
    return breakdown
