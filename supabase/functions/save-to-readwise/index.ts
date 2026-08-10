// Supabase Edge Function: proxies "Save to Readwise" clicks from the site.
//
// The Readwise token lives only here (as a Supabase secret), never in the
// browser. Supabase verifies the caller's JWT before this code runs (the
// default for Edge Functions), so only your logged-in session can trigger
// it. Deploy with:
//   supabase functions deploy save-to-readwise
//   supabase secrets set READWISE_TOKEN=your_token_here

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { url, title, summary } = await req.json();
    if (!url) {
      return new Response(JSON.stringify({ error: "Missing url" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const readwiseToken = Deno.env.get("READWISE_TOKEN");
    if (!readwiseToken) {
      return new Response(JSON.stringify({ error: "READWISE_TOKEN not configured" }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const readwiseResp = await fetch("https://readwise.io/api/v3/save/", {
      method: "POST",
      headers: {
        Authorization: `Token ${readwiseToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url, title, summary }),
    });

    const body = await readwiseResp.json();
    return new Response(JSON.stringify(body), {
      status: readwiseResp.status,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
