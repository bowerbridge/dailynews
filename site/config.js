// Not secret: this key is safe to ship in public client code — every table
// it can touch is locked down by Row Level Security to your user id only
// (see supabase/schema.sql). Uses the newer "publishable" key format from
// Settings > API; the legacy JWT anon key would work identically here too.
window.DAILY_BRIEF_CONFIG = {
  SUPABASE_URL: "https://idxshkjsmvzhiiuupxrk.supabase.co",
  SUPABASE_ANON_KEY: "sb_publishable_Sb-GDPNM_65QoPnF4dmQ_g_hZ2LjAYL",
};
