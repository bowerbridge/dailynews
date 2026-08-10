# Daily Brief

A personal daily digest: it scans your chosen websites, Substacks, and
podcasts, tags items against categories you define, emails you a summary at
7am Sydney time, and lets you rank relevance and save items to Readwise from
a small website. It also proposes new sources to follow based on your
categories.

- **Scanner** (`scanner/`) — Python, runs on a GitHub Actions schedule.
  Fetches sources, categorizes/summarizes with Claude, writes to Supabase,
  emails the digest, and discovers new candidate sources.
- **Site** (`site/`) — static HTML/JS, hosted on GitHub Pages. View today's
  digest, rank items, save to Readwise, manage sources/categories, review
  suggested sources.
- **Database** (`supabase/schema.sql`) — Postgres on Supabase. Also hosts
  the one Edge Function that proxies Readwise saves so the API token never
  reaches the browser.

Nothing depends on your Mac being on — everything runs in the cloud.

## What's out of scope in v1

- **Apple Mail newsletters**: read directly from Mail.app, since that only
  works with something running locally. Instead, add the newsletter's
  public web/RSS version as a source if it has one.
- **LinkedIn**: no supported API exists for scanning a personal feed
  without scraping (against their ToS). Revisit later if needed.
- **Obsidian**: storage is Readwise-only for now.

## One-time setup

### 1. Supabase (database + auth + edge function)

1. Create a free project at [supabase.com](https://supabase.com).
2. In the SQL Editor, run `supabase/schema.sql`. This creates the tables,
   row-level security policies, and the ranking → relevance-score trigger.
3. Go to **Authentication → Users → Add user** and create yourself an
   account (email + password) — this is the single login the site and the
   scanner's `DAILY_BRIEF_USER_ID` are scoped to.
4. Copy that new user's UUID (shown in the Users table) — you'll need it
   below as `DAILY_BRIEF_USER_ID`.
5. From **Settings → API**, note down:
   - Project URL
   - `anon` public key (safe for the browser — goes in `site/config.js`)
   - `service_role` secret key (server-only — goes in GitHub Actions secrets, never in the site)
7. Install the [Supabase CLI](https://supabase.com/docs/guides/cli) and deploy the edge function:
   ```bash
   supabase login
   supabase link --project-ref YOUR-PROJECT-REF
   supabase functions deploy save-to-readwise
   supabase secrets set READWISE_TOKEN=your_readwise_token
   ```

### 2. Readwise

Get your access token from [readwise.io/access_token](https://readwise.io/access_token).
Used both by the edge function above (for manual "Save" clicks) and by the
scanner (for auto-saving items from your consistently highly-ranked
sources).

### 3. Gmail App Password (for sending the digest)

Use an existing Gmail account (or a new one dedicated to this). With 2FA
enabled on that account, generate an [App Password](https://myaccount.google.com/apppasswords)
scoped to "Mail". That's the `GMAIL_APP_PASSWORD` secret below.

### 4. Anthropic API key

From [console.anthropic.com](https://console.anthropic.com) — used for
categorizing and summarizing items.

### 5. Site config

Edit `site/config.js` with your Supabase project URL and anon key (these
are safe to commit — every table they can touch is locked down by RLS to
your user id only).

### 6. GitHub repo + Pages + Actions secrets

I'll ask you before creating or pushing to a GitHub repo. Once you've
approved that step:

1. Push this repo to GitHub.
2. **Settings → Pages** → deploy from branch, folder `/site` (or move
   `site/` contents to repo root if you'd rather serve from `/`).
3. **Settings → Secrets and variables → Actions**, add:
   | Secret | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | from console.anthropic.com |
   | `SUPABASE_URL` | your project URL |
   | `SUPABASE_SERVICE_ROLE_KEY` | service_role key (server-only) |
   | `DAILY_BRIEF_USER_ID` | your Supabase Auth user UUID |
   | `READWISE_TOKEN` | from readwise.io/access_token |
   | `EMAIL_FROM` | the Gmail address sending the digest |
   | `EMAIL_TO` | jason_howard@me.com |
   | `GMAIL_APP_PASSWORD` | the app password from step 3 |
4. Also add a repo **variable** (not secret) `SITE_URL` set to your GitHub
   Pages URL, so the email can link back to it.

You can set secrets from the terminal instead of the GitHub UI:
```bash
gh secret set ANTHROPIC_API_KEY
gh secret set SUPABASE_URL
gh secret set SUPABASE_SERVICE_ROLE_KEY
gh secret set DAILY_BRIEF_USER_ID
gh secret set READWISE_TOKEN
gh secret set EMAIL_FROM
gh secret set EMAIL_TO
gh secret set GMAIL_APP_PASSWORD
gh variable set SITE_URL --body "https://yourusername.github.io/daily-brief/"
```
(each command prompts for the value, so nothing sensitive ends up in shell history)

### 7. Add your sources and categories

Log in to the site and use the Categories and Sources pages, or add rows
directly via `supabase/schema.sql`-style inserts. For Substack publications
you subscribe to, the feed URL is `https://PUBLICATION.substack.com/feed`.
For podcasts, use the show's RSS feed (visible in most podcast apps'
"share" or "RSS" option).

## Running it

- The scan runs automatically at 7am Sydney time (the workflow fires at
  both possible UTC offsets and no-ops at whichever one isn't currently
  7am locally, so it self-corrects across daylight saving).
- To test without waiting: **Actions → Daily Brief Scan → Run workflow**
  (runs immediately regardless of the time).
- To test the scanner locally: `cd scanner && pip install -r requirements.txt`,
  export the same env vars as the GitHub secrets above, then `python main.py`
  (set `FORCE_RUN=true` to skip the 7am check).

## How the learning works

Ranking an item 1-5 on the site updates that item's source's
`relevance_score` immediately (an exponential moving average, in a Postgres
trigger — see `apply_ranking_to_source` in `schema.sql`). The next scan uses
that score to order items and, on busy days, to trim how many items from
lower-scored sources make the cut. Sources ranked ≥0.75 with at least 5
ratings get auto-saved to Readwise without a manual click. Sources that stay
below 0.3 after 5+ ratings are flagged on the Sources page as worth
removing — never removed automatically.
