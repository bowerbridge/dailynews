import json
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

import db
import discover
import email_sender
import scoring
import sources as sources_mod
from readwise import save_document

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

# Sources ranked at/above this (with enough history) get auto-saved to
# Readwise as they come in, so your most trusted sources need no manual click.
AUTO_SAVE_THRESHOLD = 0.75
AUTO_SAVE_MIN_RANKINGS = 5


def sydney_now():
    return datetime.now(ZoneInfo("Australia/Sydney"))


def should_run_now():
    """The GitHub Actions cron fires at both possible UTC offsets for 7am
    Sydney (to survive AEST/AEDT changes) - only actually run at the one
    that's currently 7am local time. Bypassed by workflow_dispatch.
    Window is 7-9am to absorb GitHub Actions scheduling delays."""
    if os.environ.get("FORCE_RUN") == "true":
        return True
    return 7 <= sydney_now().hour <= 9


def categorize_and_summarize(entries, categories):
    """Ask Claude to pick the best-fit category (or mark irrelevant) and
    write a 1-2 sentence summary for each entry. Returns entries annotated
    with category_id and summary; irrelevant entries are dropped."""
    if not entries:
        return []

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    categories_by_name = {c["name"]: c for c in categories}

    entries_text = ""
    for i, e in enumerate(entries):
        entries_text += (
            f"\n[{i}] Title: {e['title']}\n"
            f"Source: {e['source_name']}\n"
            f"Excerpt: {e['raw_summary']}\n"
        )

    categories_str = "\n".join(f"- {c['name']}: {c['keywords']}" for c in categories)

    prompt = f"""You are curating a personal daily brief. The reader cares about
these categories only:
{categories_str}

For each item below, decide if it is genuinely relevant to one of these
categories. If it is, return its index, the best-fit category name (must
match one of the names above exactly), and a clear 1-2 sentence summary.
If an item is not relevant to any of these categories, omit it entirely.

Return ONLY a JSON array, no other text:
[{{"index": 0, "category": "Category Name", "summary": "..."}}]

Items:
{entries_text}"""

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text_block = next(b for b in response.content if b.type == "text")
    raw = text_block.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    results = json.loads(raw)

    annotated = []
    for r in results:
        entry = entries[r["index"]]
        category = categories_by_name.get(r.get("category"))
        if not category:
            continue
        entry["category_id"] = category["id"]
        entry["summary"] = r.get("summary", entry["raw_summary"])
        annotated.append(entry)

    return annotated


def maybe_auto_save(items, sources_by_id):
    for item in items:
        source = sources_by_id.get(item["source_id"], {})
        if (
            source.get("relevance_score", 0.5) >= AUTO_SAVE_THRESHOLD
            and source.get("ranking_count", 0) >= AUTO_SAVE_MIN_RANKINGS
        ):
            try:
                save_document(item["link"], title=item["title"], summary=item["summary"])
                item["saved_to_readwise"] = True
                print(f"    Auto-saved to Readwise: {item['title']}")
            except Exception as e:
                print(f"    Readwise auto-save failed for '{item['title']}': {e}")


def main():
    print(f"\n=== Daily Brief scan: {sydney_now().strftime('%A, %d %B %Y %H:%M %Z')} ===\n")

    if not should_run_now():
        print("Not 7am Sydney time yet at this cron tick - skipping (this is expected, "
              "the workflow fires at two UTC times to cover both AEST and AEDT).")
        sys.exit(0)

    categories = db.get_categories()
    sources = db.get_active_sources()
    sources_by_id = {s["id"]: s for s in sources}

    if not categories or not sources:
        print("No categories or sources configured yet - add some on the site first.")
        sys.exit(0)

    print(f"Loaded {len(categories)} categories, {len(sources)} active sources.")

    print("\nFetching entries from sources...")
    entries = sources_mod.fetch_all(sources)
    print(f"\nTotal candidate entries: {len(entries)}")

    print("\nCategorizing and summarizing with Claude...")
    items = categorize_and_summarize(entries, categories)
    print(f"  {len(items)} relevant items after filtering")

    items = scoring.cap_items_per_source(items, sources_by_id)
    items = scoring.order_items(items, sources_by_id)

    print("\nChecking for Readwise auto-save candidates...")
    maybe_auto_save(items, sources_by_id)

    print("\nSaving items to database...")
    scan_date = sydney_now().date().isoformat()
    db_rows = [
        {
            "source_id": item["source_id"],
            "category_id": item["category_id"],
            "title": item["title"],
            "url": item["link"],
            "summary": item["summary"],
            "published_at": item["published_at"],
            "scan_date": scan_date,
            "saved_to_readwise": item.get("saved_to_readwise", False),
        }
        for item in items
    ]
    db.insert_items(db_rows)

    print("\nDiscovering new candidate sources for your categories...")
    known_urls = db.get_all_source_feed_urls()
    suggestions = discover.discover_all(categories, known_urls)
    db.insert_suggested_sources(suggestions)
    print(f"  {len(suggestions)} suggestion(s) recorded")

    weak = scoring.flag_weak_sources(sources)
    if weak:
        print(f"\n{len(weak)} source(s) consistently ranked low - flagged for review on the site:")
        for s in weak:
            print(f"  - {s['name']} (score {s['relevance_score']:.2f}, {s['ranking_count']} rankings)")

    print("\nBuilding and sending email...")
    categories_by_id = {c["id"]: c for c in categories}
    date_str = sydney_now().strftime("%A, %d %B %Y")
    for item in items:
        item["url"] = item["link"]
    html = email_sender.build_html(items, categories_by_id, date_str)
    email_sender.send_email(html, date_str)

    print("\nDone!")


if __name__ == "__main__":
    main()
