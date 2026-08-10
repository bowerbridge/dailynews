"""Build and send the 7am digest email.

Generalizes the original ai-news-digest build_html/send_email: instead of a
fixed list of AI categories, items are grouped by whatever categories exist
in your `categories` table. Each item shows title, short summary, source,
and a link back to the original — ranking and saving happen on the site,
not in the email.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SITE_URL = os.environ.get("SITE_URL", "")


def group_by_category(items, categories_by_id):
    grouped = {}
    for item in items:
        cat_name = categories_by_id.get(item.get("category_id"), {}).get("name", "Uncategorized")
        grouped.setdefault(cat_name, []).append(item)
    return grouped


def build_html(items, categories_by_id, date_str):
    grouped = group_by_category(items, categories_by_id)
    total = len(items)

    sections_html = ""
    for cat_name, cat_items in grouped.items():
        entries = ""
        for item in cat_items:
            entries += f"""
            <div class="article">
              <div class="article-title"><a href="{item['url']}">{item['title']}</a></div>
              <div class="article-summary">{item['summary']}</div>
              <div class="article-meta">
                {item['source_name']} &nbsp;&bull;&nbsp; {item.get('date_display', '')}
                &nbsp;&bull;&nbsp; <a href="{item['url']}">Read more &rarr;</a>
              </div>
            </div>"""
        sections_html += f"""
        <div class="section">
          <div class="section-header">{cat_name}</div>
          {entries}
        </div>"""

    no_items = (
        ""
        if total
        else '<p style="color:#888;font-style:italic;padding:24px 0;">No new items today.</p>'
    )

    site_link = (
        f'<div class="stats"><a href="{SITE_URL}" style="color:#93c5fd;">Rank &amp; save items on the site &rarr;</a></div>'
        if SITE_URL
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
          background: #f0f2f5; color: #1a1a1a; }}
  .wrapper {{ max-width: 680px; margin: 0 auto; }}
  .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
             color: white; padding: 32px 40px; }}
  .header h1 {{ font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }}
  .header .subtitle {{ margin-top: 6px; font-size: 13px; color: #94a3b8; }}
  .stats {{ background: #1e293b; color: #94a3b8; padding: 10px 40px; font-size: 12px; }}
  .body {{ background: white; padding: 8px 40px 40px; }}
  .section {{ margin-top: 32px; }}
  .section-header {{ font-size: 11px; font-weight: 700; text-transform: uppercase;
                     letter-spacing: 1.5px; color: #64748b; padding-bottom: 10px;
                     border-bottom: 2px solid #e2e8f0; margin-bottom: 16px; }}
  .article {{ padding: 16px 0; border-bottom: 1px solid #f1f5f9; }}
  .article:last-child {{ border-bottom: none; }}
  .article-title {{ font-size: 15px; font-weight: 600; line-height: 1.4; margin-bottom: 6px; }}
  .article-title a {{ color: #0f172a; text-decoration: none; }}
  .article-title a:hover {{ color: #2563eb; text-decoration: underline; }}
  .article-summary {{ font-size: 13px; color: #475569; line-height: 1.6; margin-bottom: 8px; }}
  .article-meta {{ font-size: 11px; color: #94a3b8; }}
  .article-meta a {{ color: #2563eb; text-decoration: none; }}
  .footer {{ background: #f8fafc; padding: 20px 40px; text-align: center;
             font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Daily Brief</h1>
    <div class="subtitle">{date_str}</div>
  </div>
  {site_link}
  <div class="body">
    {sections_html}
    {no_items}
  </div>
  <div class="footer">{total} item{'s' if total != 1 else ''} &bull; {date_str}</div>
</div>
</body>
</html>"""


def send_email(html, date_str):
    from_addr = os.environ["EMAIL_FROM"]
    to_addr = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Brief: {date_str}"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_addr, os.environ["GMAIL_APP_PASSWORD"])
        server.send_message(msg)

    print(f"  Email sent to {to_addr}")
