"""Minimal Readwise Reader client.

Used server-side by the scanner to auto-save items from sources you've
consistently ranked highly (see AUTO_SAVE_THRESHOLD in main.py). Manual
"Save" clicks from the site go through the separate Supabase Edge Function
(supabase/functions/save-to-readwise) instead, so the token never has to be
exposed to the browser — this module only ever runs in GitHub Actions.
"""

import os
import requests

READWISE_TOKEN = os.environ.get("READWISE_TOKEN")
SAVE_URL = "https://readwise.io/api/v3/save/"


def save_document(url, title=None, summary=None, tags=None):
    if not READWISE_TOKEN:
        raise RuntimeError("READWISE_TOKEN is not set")

    payload = {"url": url}
    if title:
        payload["title"] = title
    if summary:
        payload["summary"] = summary
    if tags:
        payload["tags"] = tags

    resp = requests.post(
        SAVE_URL,
        headers={"Authorization": f"Token {READWISE_TOKEN}"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
