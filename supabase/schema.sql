-- Daily Brief schema
-- Run this in the Supabase SQL editor for a new project (SQL Editor > New
-- query > paste this whole file > Run). Safe to run once, top to bottom.
-- Single-user app: every table is scoped to auth.uid() via RLS so only the
-- logged-in user (you) can read or write anything, even though the anon key
-- ships in the public site's JS.

create extension if not exists "pgcrypto";

-- ── categories ────────────────────────────────────────────────
create table categories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name text not null,
  keywords text not null default '',   -- used by discover.py as a search query seed
  created_at timestamptz not null default now(),
  unique (user_id, name)
);

-- ── sources ───────────────────────────────────────────────────
create table sources (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name text not null,
  url text not null,             -- homepage / canonical link
  feed_url text not null,        -- RSS/Atom feed actually polled
  type text not null default 'website' check (type in ('website', 'substack', 'podcast', 'other')),
  relevance_score double precision not null default 0.5,  -- learned via scoring.py EMA
  ranking_count integer not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table source_categories (
  source_id uuid not null references sources(id) on delete cascade,
  category_id uuid not null references categories(id) on delete cascade,
  primary key (source_id, category_id)
);

-- ── items (scanned articles/episodes) ────────────────────────
create table items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  source_id uuid not null references sources(id) on delete cascade,
  category_id uuid references categories(id) on delete set null,
  title text not null,
  url text not null,
  summary text not null default '',
  published_at timestamptz,
  scan_date date not null default current_date,
  saved_to_readwise boolean not null default false,
  created_at timestamptz not null default now(),
  unique (user_id, url, scan_date)
);

-- ── rankings (one row per rank action on an item) ────────────
create table rankings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  item_id uuid not null references items(id) on delete cascade,
  source_id uuid not null references sources(id) on delete cascade,
  score smallint not null check (score between 1 and 5),
  created_at timestamptz not null default now()
);

-- ── suggested_sources (discovered by discover.py) ────────────
create table suggested_sources (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name text not null,
  url text not null,
  feed_url text,
  category_id uuid references categories(id) on delete set null,
  status text not null default 'pending' check (status in ('pending', 'added', 'dismissed')),
  discovered_at timestamptz not null default now(),
  unique (user_id, url)
);

-- ── RLS: every table only visible/writable by its owning user ─
alter table categories enable row level security;
alter table sources enable row level security;
alter table source_categories enable row level security;
alter table items enable row level security;
alter table rankings enable row level security;
alter table suggested_sources enable row level security;

create policy "owner full access" on categories
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "owner full access" on sources
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "owner full access" on items
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "owner full access" on rankings
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "owner full access" on suggested_sources
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- source_categories has no user_id of its own; gate through the parent source
create policy "owner full access via source" on source_categories
  for all
  using (exists (select 1 from sources s where s.id = source_id and s.user_id = auth.uid()))
  with check (exists (select 1 from sources s where s.id = source_id and s.user_id = auth.uid()));

-- ── learning: update source relevance_score on every rank action ─
-- Runs immediately when the site inserts a ranking (score 1-5), so learning
-- happens in real time rather than waiting for the next scan.
create or replace function apply_ranking_to_source()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  alpha double precision := 0.2;       -- weight given to the new rank
  normalized double precision;
begin
  normalized := (new.score - 1) / 4.0; -- maps 1..5 -> 0..1
  update sources
    set relevance_score = relevance_score * (1 - alpha) + normalized * alpha,
        ranking_count = ranking_count + 1
    where id = new.source_id;
  return new;
end;
$$;

create trigger rankings_update_source_score
  after insert on rankings
  for each row execute function apply_ranking_to_source();

-- ── helpful indexes ───────────────────────────────────────────
create index items_scan_date_idx on items (user_id, scan_date desc);
create index rankings_source_idx on rankings (source_id);
create index suggested_status_idx on suggested_sources (user_id, status);

-- No seed data here on purpose: this script runs in the SQL Editor as a
-- superuser with no logged-in app user, so auth.uid() is NULL there and
-- any insert relying on it (every table above) would fail its not-null
-- constraint. Add your starter categories/sources from the site instead,
-- once you've created your Auth user and logged in — see README.md.
-- (If you really want to seed via SQL, insert explicit user_id values
-- using the UUID from Authentication > Users, e.g.:
--   insert into categories (user_id, name, keywords) values
--     ('00000000-0000-0000-0000-000000000000', 'AI & Technology', 'artificial intelligence machine learning');
-- )
