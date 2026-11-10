// shko capture-API Worker (#40/#41)
//
// POST {url, mode?, name?} -> renders the page in Cloudflare Browser Run
// (managed headless Chromium), classifies the result with the SAME
// challenge-detection as scripts/capture_page.py, and on success stores a
// full-page screenshot + rendered HTML + a provenance record in R2. Tier-0
// (cooperative sites) only; bot-walled Tier-1 and authenticated Tier-2 captures
// stay on the local/residential path (see reports/capture-pipeline.md).
//
// Bindings (wrangler.toml): BROWSER (Browser Rendering), ARCHIVE (R2 bucket).

import puppeteer from "@cloudflare/puppeteer";

// Keep in sync with scripts/capture_page.py / fetch_extract.py.
// STRONG markers only appear on an actual interstitial — a hit means blocked.
const STRONG_MARKERS = [
  "performing security verification",
  "checking your browser before accessing",
  "just a moment...",
  "attention required! | cloudflare",
  "ddos protection by cloudflare",
  "enable javascript and cookies to continue",
  "verify you are human",
  "verifying you are human",
];
// WEAK markers (Cloudflare challenge/turnstile script tags) also appear in
// legit Cloudflare-fronted pages, so they only indicate a block on a small page.
const WEAK_MARKERS = ["cf-browser-verification", "challenge-platform", "__cf_chl", "cf_chl_opt"];
const SMALL_PAGE = 15000;

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

// Constant-time string compare for the auth token.
function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Defence-in-depth: refuse internal / link-local / metadata targets even for an
// authenticated caller, so the worker can't be turned into an SSRF tool.
const BLOCKED_HOST =
  /^(localhost$|127\.|0\.0\.0\.0$|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|\[?::1\]?$|.*\.internal$|.*\.local$|metadata\.)/i;

function hostOf(url) {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return "unknown";
  }
}

async function sha256hex(buf) {
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return json({ error: "POST {url, mode?, name?}" }, 405);
    }
    // Auth gate — reject BEFORE spending any Browser Run / R2.
    if (!env.CAPTURE_TOKEN) {
      return json({ error: "server misconfigured: no CAPTURE_TOKEN set" }, 500);
    }
    const provided =
      request.headers.get("x-capture-token") ||
      (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
    if (!safeEqual(provided, env.CAPTURE_TOKEN)) {
      return json({ error: "unauthorized" }, 401);
    }
    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "invalid JSON body" }, 400);
    }
    const { url, mode = "screenshot", name } = body || {};
    if (!url || !/^https?:\/\//.test(url)) {
      return json({ error: "a http(s) url is required" }, 400);
    }
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      return json({ error: "unparseable url" }, 400);
    }
    if (BLOCKED_HOST.test(parsed.hostname)) {
      return json({ error: "blocked host (internal/link-local)" }, 400);
    }

    // Launch guard: Browser Run can refuse a new browser (instance/rate limit).
    // Returning a clean 503 lets the client retry, instead of an Error 1101 crash.
    let browser;
    try {
      browser = await puppeteer.launch(env.BROWSER);
    } catch (err) {
      return json(
        { url, status: "error", note: "browser launch failed: " + String(err) },
        503,
      );
    }
    try {
      const page = await browser.newPage();
      await page.setViewport({ width: 1280, height: 1600 });
      const resp = await page.goto(url, {
        waitUntil: "networkidle0",
        timeout: 30000,
      });
      const html = await page.content();
      const low = html.toLowerCase();

      let status = "ok";
      let note = "rendered page content present";
      if (STRONG_MARKERS.some((m) => low.includes(m))) {
        status = "blocked";
        note = "interstitial challenge";
      } else if (html.replace(/<[^>]+>/g, " ").trim().length < 200) {
        status = "dead";
        note = "empty/near-empty DOM (no render)";
      } else if (html.length < SMALL_PAGE && WEAK_MARKERS.some((m) => low.includes(m))) {
        status = "blocked";
        note = "challenge script on a small page";
      }

      const png = await page.screenshot({ fullPage: true });
      const sha = await sha256hex(png);
      const base = `screenshots/${name || hostOf(url)}/${Date.now()}`;
      const key = `${base}.png`;

      const record = {
        url,
        mode,
        status,
        note,
        captured_at: new Date().toISOString(),
        http_status: resp ? resp.status() : null,
        screenshot: status === "ok" ? key : null,
        screenshot_bytes: png.length,
        screenshot_sha256: sha,
      };

      // Only store a real page as the archive; challenge/dead captures are
      // reported, not persisted as artifacts.
      if (status === "ok") {
        await env.ARCHIVE.put(key, png, {
          httpMetadata: { contentType: "image/png" },
        });
        await env.ARCHIVE.put(`${base}.html`, html, {
          httpMetadata: { contentType: "text/html; charset=utf-8" },
        });
      }
      await env.ARCHIVE.put(`${base}.json`, JSON.stringify(record, null, 2), {
        httpMetadata: { contentType: "application/json" },
      });

      return json(record, status === "ok" ? 200 : 422);
    } catch (err) {
      return json({ url, status: "error", note: String(err) }, 502);
    } finally {
      try {
        await browser.close();
      } catch {
        /* ignore close errors */
      }
    }
  },
};
