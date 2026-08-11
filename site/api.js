// Shared Supabase client + data helpers used by every page.
const { SUPABASE_URL, SUPABASE_ANON_KEY } = window.DAILY_BRIEF_CONFIG;
const sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Redirect to login.html if there's no active session. Call at the top of
// every protected page. Returns the session's user.
async function requireAuth() {
  const { data: { session } } = await sb.auth.getSession();
  if (!session) {
    window.location.href = "login.html";
    return null;
  }
  return session.user;
}

async function signOut() {
  await sb.auth.signOut();
  window.location.href = "login.html";
}

// ── categories ───────────────────────────────────────────────

async function listCategories() {
  const { data, error } = await sb.from("categories").select("*").order("name");
  if (error) throw error;
  return data;
}

async function addCategory(name, keywords) {
  const { error } = await sb.from("categories").insert({ name, keywords });
  if (error) throw error;
}

async function updateCategory(id, name, keywords) {
  const { error } = await sb.from("categories").update({ name, keywords }).eq("id", id);
  if (error) throw error;
}

async function deleteCategory(id) {
  const { error } = await sb.from("categories").delete().eq("id", id);
  if (error) throw error;
}

// ── sources ──────────────────────────────────────────────────

async function listSources() {
  const { data, error } = await sb.from("sources").select("*").order("relevance_score", { ascending: false });
  if (error) throw error;
  return data;
}

async function addSource({ name, url, feed_url, type, category_id }) {
  const { data, error } = await sb.from("sources").insert({ name, url, feed_url, type }).select().single();
  if (error) throw error;
  if (category_id) {
    await sb.from("source_categories").insert({ source_id: data.id, category_id });
  }
  return data;
}

async function setSourceActive(id, active) {
  const { error } = await sb.from("sources").update({ active }).eq("id", id);
  if (error) throw error;
}

async function deleteSource(id) {
  const { error } = await sb.from("sources").delete().eq("id", id);
  if (error) throw error;
}

// ── today's items ────────────────────────────────────────────

async function getTodayItems() {
  // "today" from the item's own scan_date, so this works no matter what
  // time zone the browser is in relative to when the scan ran.
  const { data: latest } = await sb
    .from("items")
    .select("scan_date")
    .order("scan_date", { ascending: false })
    .limit(1)
    .single();

  if (!latest) return [];

  const { data, error } = await sb
    .from("items")
    .select("*, sources(name, url, relevance_score), categories(name)")
    .eq("scan_date", latest.scan_date)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data;
}

async function rankItem(itemId, sourceId, score) {
  const { error } = await sb.from("rankings").insert({ item_id: itemId, source_id: sourceId, score });
  if (error) throw error;
}

async function saveItemToReadwise(item) {
  const { data, error } = await sb.functions.invoke("save-to-readwise", {
    body: { url: item.url, title: item.title, summary: item.summary },
  });
  if (error) throw error;
  await sb.from("items").update({ saved_to_readwise: true }).eq("id", item.id);
  return data;
}

// ── archive (every past scan, grouped by date) ────────────────

async function listArchiveDates() {
  // Just the date column across all items - cheap even after months of
  // history - grouped client-side into counts per day. Excludes the most
  // recent scan_date, which is "Today" and lives on index.html instead.
  const { data, error } = await sb.from("items").select("scan_date");
  if (error) throw error;

  const counts = {};
  for (const row of data) counts[row.scan_date] = (counts[row.scan_date] || 0) + 1;

  const dates = Object.entries(counts)
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => b.date.localeCompare(a.date));

  return dates.slice(1); // drop today
}

async function getItemsForDate(date) {
  const { data, error } = await sb
    .from("items")
    .select("*, sources(name, url, relevance_score), categories(name)")
    .eq("scan_date", date)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data;
}

// ── suggested sources ────────────────────────────────────────

async function listSuggested() {
  const { data, error } = await sb
    .from("suggested_sources")
    .select("*, categories(name)")
    .eq("status", "pending")
    .order("discovered_at", { ascending: false });
  if (error) throw error;
  return data;
}

async function acceptSuggestion(suggestion) {
  await addSource({
    name: suggestion.name,
    url: suggestion.url,
    feed_url: suggestion.feed_url || suggestion.url,
    type: "website",
    category_id: suggestion.category_id,
  });
  const { error } = await sb.from("suggested_sources").update({ status: "added" }).eq("id", suggestion.id);
  if (error) throw error;
}

async function dismissSuggestion(id) {
  const { error } = await sb.from("suggested_sources").update({ status: "dismissed" }).eq("id", id);
  if (error) throw error;
}
