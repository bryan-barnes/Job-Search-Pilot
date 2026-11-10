// Cloudflare Email Worker for your alerts address (e.g. alerts@yourdomain.com).
// Keeps only LinkedIn job emails (forwarded by a Gmail filter) and Gmail's
// one-time forwarding confirmation. Everything else is rejected, never stored.
// Stored emails expire after 30 days. Reading them requires the ALERTS_TOKEN secret.

const KEEP_FOR_SECONDS = 60 * 60 * 24 * 30;

function senderOf(message) {
  const from = message.headers.get("from") || "";
  const inBrackets = from.match(/<([^>]+)>/);
  return (inBrackets ? inBrackets[1] : from).trim().toLowerCase();
}

export default {
  async email(message, env) {
    const sender = senderOf(message);
    const allowed =
      sender.endsWith("@linkedin.com") || sender === "forwarding-noreply@google.com";
    if (!allowed) {
      message.setReject("This address only accepts job alerts.");
      return;
    }
    if (message.rawSize > 5_000_000) {
      message.setReject("Message too large.");
      return;
    }
    const raw = await new Response(message.raw).text();
    const key = `msg:${new Date().toISOString()}:${crypto.randomUUID().slice(0, 8)}`;
    await env.ALERTS.put(key, raw, {
      expirationTtl: KEEP_FOR_SECONDS,
      metadata: {
        from: sender,
        subject: (message.headers.get("subject") || "").slice(0, 300),
      },
    });
  },

  async fetch(request, env) {
    const auth = request.headers.get("authorization") || "";
    if (!env.ALERTS_TOKEN || auth !== `Bearer ${env.ALERTS_TOKEN}`) {
      return new Response("Not found", { status: 404 });
    }
    const url = new URL(request.url);
    if (url.pathname === "/list") {
      const list = await env.ALERTS.list({ prefix: "msg:" });
      return Response.json(list.keys.map((k) => ({ key: k.name, ...k.metadata })));
    }
    if (url.pathname === "/msg") {
      const key = url.searchParams.get("key") || "";
      if (!key.startsWith("msg:")) return new Response("Bad key", { status: 400 });
      const raw = await env.ALERTS.get(key);
      if (raw === null) return new Response("Gone", { status: 404 });
      return new Response(raw, { headers: { "content-type": "text/plain; charset=utf-8" } });
    }
    return new Response("Not found", { status: 404 });
  },
};
