"""Thin Supabase REST client for the scanner.

Uses the service-role key so it bypasses RLS (the scanner runs as a trusted
backend job, not as the logged-in user). Talks to PostgREST directly over
HTTPS rather than pulling in the full supabase-py SDK, to keep the
requirements list small.
"""

import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
# All rows are scoped to this one user id (see README for how to find it).
USER_ID = os.environ["DAILY_BRIEF_USER_ID"]

REST_URL = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}


def _get(path, params=None):
    resp = requests.get(f"{REST_URL}/{path}", headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path, rows, upsert_on=None):
    headers = dict(HEADERS)
    prefer = "return=representation"
    if upsert_on:
        prefer = f"resolution=merge-duplicates,{prefer}"
        path = f"{path}?on_conflict={upsert_on}"
    headers["Prefer"] = prefer
    resp = requests.post(f"{REST_URL}/{path}", headers=headers, json=rows, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _patch(path, params, body):
    headers = dict(HEADERS)
    headers["Prefer"] = "return=representation"
    resp = requests.patch(f"{REST_URL}/{path}", headers=headers, params=params, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── categories ───────────────────────────────────────────────

def get_categories():
    return _get("categories", {"user_id": f"eq.{USER_ID}", "select": "*"})


# ── sources ──────────────────────────────────────────────────

def get_active_sources():
    return _get(
        "sources",
        {"user_id": f"eq.{USER_ID}", "active": "eq.true", "select": "*"},
    )


def get_all_source_feed_urls():
    """Used by discover.py to avoid suggesting sources we already track."""
    rows = _get("sources", {"user_id": f"eq.{USER_ID}", "select": "url,feed_url"})
    urls = set()
    for r in rows:
        urls.add(r["url"])
        urls.add(r["feed_url"])
    return urls


def update_source_score(source_id, new_score, ranking_count):
    _patch(
        "sources",
        {"id": f"eq.{source_id}"},
        {"relevance_score": new_score, "ranking_count": ranking_count},
    )


# ── items ────────────────────────────────────────────────────

def insert_items(items):
    """items: list of dicts with source_id, category_id, title, url, summary,
    published_at, scan_date. Skips duplicates (same user+url+scan_date)."""
    if not items:
        return []
    for i in items:
        i["user_id"] = USER_ID
    return _post("items", items, upsert_on="user_id,url,scan_date")


# ── rankings (read, for scoring.py) ─────────────────────────

def get_rankings_since(iso_timestamp):
    return _get(
        "rankings",
        {"user_id": f"eq.{USER_ID}", "created_at": f"gte.{iso_timestamp}", "select": "*"},
    )


# ── suggested sources ────────────────────────────────────────

def insert_suggested_sources(rows):
    if not rows:
        return []
    for r in rows:
        r["user_id"] = USER_ID
    return _post("suggested_sources", rows, upsert_on="user_id,url")
