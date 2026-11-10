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

// Keep this list in sync with CHALLENGE_MARKERS in scripts/capture_page.py.
const CHALLENGE_MARKERS = [
  "performing security verification",
  "checking your browser before accessing",
  "cf-browser-verification",
  "challenge-platform",
  "__cf_chl",
  "cf_chl_opt",
  "just a moment...",
  "attention required! | cloudflare",
  "ddos protection by cloudflare",
  "enable javascript and cookies to continue",
  "verify you are human",
  "verifying you are human",
];

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

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

    const browser = await puppeteer.launch(env.BROWSER);
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
      for (const m of CHALLENGE_MARKERS) {
        if (low.includes(m)) {
          status = "blocked";
          note = `challenge marker: ${m}`;
          break;
        }
      }
      if (status === "ok" && html.replace(/<[^>]+>/g, " ").trim().length < 200) {
        status = "dead";
        note = "empty/near-empty DOM (no render)";
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
      await browser.close();
    }
  },
};
