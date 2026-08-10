"""Use each source's learned relevance_score to order/prioritize items.

The score itself is updated in real time by a Postgres trigger
(`apply_ranking_to_source` in supabase/schema.sql) whenever you rank an item
on the site, as an exponential moving average of your 1-5 ratings normalized
to 0-1. This module just consumes that score at scan time — it doesn't
recompute it, so learning applies immediately rather than only on the next
day's run.
"""

LOW_SCORE_THRESHOLD = 0.3
MIN_RANKINGS_BEFORE_FLAGGING = 5
MAX_ITEMS_PER_SOURCE_WHEN_BUSY = 8
BUSY_THRESHOLD = 40  # total items across all sources today


def order_items(items, sources_by_id):
    """Sort items by their source's relevance_score, descending. Items from
    unranked sources (score still at the 0.5 default) land in the middle."""
    def key(item):
        source = sources_by_id.get(item["source_id"], {})
        return source.get("relevance_score", 0.5)

    return sorted(items, key=key, reverse=True)


def cap_items_per_source(items, sources_by_id):
    """When there's a lot of volume today, trim low-relevance sources down
    rather than dropping them entirely, so nothing goes unnoticed forever."""
    if len(items) <= BUSY_THRESHOLD:
        return items

    by_source = {}
    for item in items:
        by_source.setdefault(item["source_id"], []).append(item)

    trimmed = []
    for source_id, source_items in by_source.items():
        score = sources_by_id.get(source_id, {}).get("relevance_score", 0.5)
        limit = MAX_ITEMS_PER_SOURCE_WHEN_BUSY if score >= 0.5 else max(2, MAX_ITEMS_PER_SOURCE_WHEN_BUSY // 2)
        trimmed.extend(source_items[:limit])

    return trimmed


def flag_weak_sources(sources):
    """Sources with enough ranking history but a persistently low score —
    surfaced on the Sources page as 'consider removing', never auto-removed."""
    return [
        s for s in sources
        if s.get("ranking_count", 0) >= MIN_RANKINGS_BEFORE_FLAGGING
        and s.get("relevance_score", 0.5) < LOW_SCORE_THRESHOLD
    ]
