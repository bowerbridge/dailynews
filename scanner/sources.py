"""Fetch recent entries from RSS/Atom feeds.

Covers websites, Substack publications, and podcasts — all three publish a
standard RSS/Atom feed, so a single feedparser-based fetch works for all of
them. `source["type"]` is carried through for display purposes only.
"""

import re
from datetime import datetime, timezone, timedelta

import feedparser
import requests
from dateutil import parser as dateutil_parser

LOOKBACK_HOURS = 30  # a little over 24h to tolerate scan-time drift
REQUEST_TIMEOUT = 10  # seconds
USER_AGENT = "Mozilla/5.0 (compatible; DailyBriefBot/1.0)"


def fetch_feed(url):
    """Fetch and parse a feed with a hard timeout. feedparser.parse(url) has
    no timeout of its own when given a URL directly, which can hang a scan
    indefinitely on a slow/unresponsive domain - so fetch the bytes
    ourselves first and hand those to feedparser instead."""
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def clean_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_date(entry):
    for field in ("published", "updated", "created"):
        if hasattr(entry, field):
            try:
                dt = dateutil_parser.parse(getattr(entry, field))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def fetch_source_entries(source):
    """source: row from the `sources` table (id, name, feed_url, type, ...).
    Returns a list of raw candidate items, not yet categorized/summarized."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    entries = []

    try:
        feed = fetch_feed(source["feed_url"])
    except Exception as e:
        print(f"  Error fetching {source['name']}: {e}")
        return entries

    for entry in feed.entries:
        pub_date = parse_date(entry)
        if pub_date and pub_date < cutoff:
            continue

        title = clean_html(entry.get("title", ""))
        raw_summary = clean_html(entry.get("summary", entry.get("description", "")))[:600]
        link = entry.get("link", "") or entry.get("id", "")

        if not title or not link:
            continue

        entries.append({
            "title": title,
            "raw_summary": raw_summary,
            "link": link,
            "source_id": source["id"],
            "source_name": source["name"],
            "source_type": source.get("type", "website"),
            "published_at": pub_date.isoformat() if pub_date else None,
            "date_display": pub_date.strftime("%d %b %Y") if pub_date else "Today",
        })

    return entries


def fetch_all(sources):
    """sources: list of active source rows from Supabase."""
    all_entries = []
    for source in sources:
        print(f"  Fetching {source['name']} ({source.get('type', 'website')})...")
        entries = fetch_source_entries(source)
        print(f"    {len(entries)} recent entries found")
        all_entries.extend(entries)
    return all_entries
