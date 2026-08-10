"""Discover candidate new sources for each of your categories.

Generalizes the Google-News-RSS-search pattern from the original
ai-news-digest (`fetch_topic_articles` / `trusted_research_domains`): for
each category, search Google News using its `keywords`, collect the distinct
publisher domains that show up, skip ones you already track, and try to
resolve a working RSS feed for the rest. Results are written to
`suggested_sources` for you to Add/Dismiss on the site — nothing is added
automatically.
"""

import urllib.parse
from urllib.parse import urlparse

import feedparser

COMMON_FEED_PATHS = ["/feed", "/rss", "/rss.xml", "/feed.xml", "/feeds/posts/default"]
MAX_CANDIDATES_PER_CATEGORY = 5


def _domain_of(url):
    try:
        netloc = urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def _try_resolve_feed(homepage_url):
    """Best-effort: try the homepage itself, then a few common feed paths."""
    candidates = [homepage_url] + [
        homepage_url.rstrip("/") + p for p in COMMON_FEED_PATHS
    ]
    for candidate in candidates:
        try:
            feed = feedparser.parse(candidate)
            if feed.entries:
                return candidate
        except Exception:
            continue
    return None


def discover_for_category(category, known_urls):
    """category: row from `categories` table (id, name, keywords).
    known_urls: set of urls/feed_urls already tracked, to skip."""
    query = category["keywords"] or category["name"]
    search_url = (
        "https://news.google.com/rss/search?"
        f"q={urllib.parse.quote(query)}&hl=en&gl=US&ceid=US:en"
    )

    print(f"  Discovering sources for '{category['name']}'...")
    suggestions = []
    seen_domains = set()

    try:
        feed = feedparser.parse(search_url)
    except Exception as e:
        print(f"    Error searching: {e}")
        return suggestions

    for entry in feed.entries:
        if len(suggestions) >= MAX_CANDIDATES_PER_CATEGORY:
            break

        link = entry.get("link", "")
        source_title = ""
        if hasattr(entry, "source") and hasattr(entry.source, "title"):
            source_title = entry.source.title
            source_href = getattr(entry.source, "href", link)
        else:
            source_href = link

        domain = _domain_of(source_href)
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)

        homepage = f"https://{domain}"
        if homepage in known_urls or any(domain in u for u in known_urls):
            continue

        feed_url = _try_resolve_feed(homepage)
        if not feed_url:
            continue

        suggestions.append({
            "name": source_title or domain,
            "url": homepage,
            "feed_url": feed_url,
            "category_id": category["id"],
        })

    print(f"    {len(suggestions)} new candidate source(s) found")
    return suggestions


def discover_all(categories, known_urls):
    all_suggestions = []
    for category in categories:
        all_suggestions.extend(discover_for_category(category, known_urls))
    return all_suggestions
