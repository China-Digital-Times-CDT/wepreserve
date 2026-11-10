# Capture pipeline — design & policy

On-demand capture machinery for growing the archive without it being hostage to
one local machine being awake, and without paying to run anything as an
always-on service. Tracks GitHub milestone **"Capture pipeline: full functional
release"** (#40 umbrella · #41 Browser Run · #42 Container+Browsertrix · #43
this policy · #36 reference capture).

This is the authoritative spec for the pipeline; the issues hold the task
detail. Written 2026-11-10.

## The core idea: capture is tiered, and the edge is not a silver bullet

Capture is **not one happy path**. A liveness probe of real targets on
2026-11-10 hit every tier at once:

| Tier | Example | What happens | Who captures it |
|---|---|---|---|
| **0 — cooperative** | pori.hk, photonmedia.net (`200`) | renders anywhere | edge Browser Run (#41) / container Browsertrix (#42) |
| **1 — bot-walled** | hongkongfp.com (`403` to curl), hkja.org.hk (Cloudflare challenge) | needs a *real browser*; datacenter IPs still blocked | **local/residential** real-browser (`capture_page.py`) |
| **2 — authenticated** | BoomheadNews (Facebook cookies) | needs a logged-in session | **local only**, cookies never on edge (#43) |
| **3 — gone** | hkitwu.org, neodemocrats.org.hk (`000`) | live site already dead | Wayback / existing WACZ only |

**Consequence:** the Cloudflare edge handles the easy *volume* (Tier 0); the
**local/residential real-browser path is the robustness backbone** for Tiers 1–2
— and it needs no Cloudflare at all. Tier 3 is why we capture *proactively*.

## Tools

- **`scripts/capture_page.py`** — single-page capture in a real headless Chrome.
  Writes a full-page screenshot + rendered DOM + provenance JSON (url, UTC time,
  sha256s, sizes). **Classifies every result** so we never store a bot-wall as
  the archive: `ok` (stored) / `blocked` (challenge wall — renamed aside) /
  `dead` (nothing rendered). The Tier-1 backbone and the per-URL engine.
- **`scripts/capture_refs.py`** (#36) — walks the vault, extracts external
  citation URLs (skipping infra: Wayback, IPFS, our R2/site, GitHub, library/
  video/Wikipedia lookups), and cold-captures each (local or via the edge
  `--worker`), writing a manifest. Gives us a dated, hash-verified copy of every
  source we cite.
- **`scripts/fetch_extract.py`** — the **Tier-1 full-text engine**, technique
  ported from the here.news Forensic Center (hybrid decision, 2026-11-10): a
  `curl_cffi` browser-TLS-impersonation fetch + `trafilatura` clean-text
  extraction. It reaches sites that bot-wall every lighter method — validated
  2026-11-10: it fetched **The Witness** (a real article at HTTP 200 with
  **2,542 chars of clean full text**, plus title/author/date) and passiontimes,
  where plain curl / urllib / headless Browsertrix all got 403. Deps in
  `scripts/requirements-capture.txt` (own venv; no coupling to here.news's
  Postgres/GCS). Sites behind a *real* JS challenge (e.g. hkja's Cloudflare
  interstitial) still return `blocked` — those need the stealth headful-browser
  fallback (next increment) or the Internet Archive. **Public pages only.**
  Classifier note: a page is only `blocked` on a STRONG interstitial phrase or a
  small/4xx page — a large 200 that merely embeds Cloudflare's `challenge-platform`
  script (as thewitnesshk.com does) is the real page, not a block.
- **Cloudflare Browser Run** (#41) — managed headless Chromium (REST
  `/screenshot` + PDF + HTML). The Tier-0 *cloud* variant of `capture_page`: no
  container to maintain. (Formerly "Browser Rendering"; renamed Apr 2026.)
- **Browsertrix Crawler** (#42) — in an on-demand Cloudflare Container, for heavy
  whole-site WACZ crawls; `--generateWACZ` with built-in S3 upload to R2 +
  webhook; idles to zero. Unauthenticated sites only.
- **`scripts/r2-sync-wacz.sh`** — ingest path to R2 (sha256 → rclone, single-
  stream fallback). Plus `wacz-strip-cookies.sh` / `wacz-verify-nocookies.py`
  for the authenticated captures.

## Hardening requirements (hard-won on BoomheadNews, re-proven 2026-11-10)

1. **Browser-engine capture, not HTTP** — 403/429 fall to a real browser;
   **detect a block/challenge page and never store it.** (`capture_page` caught
   hkja's Cloudflare "performing security verification" page and set it aside.)
2. **Classify every failure** (`403`/challenge vs `000` vs timeout) so we know
   whether to retry-via-residential or escalate to Wayback — never silently
   store an error page.
3. **Transport resilience** — big WACZ over a thin/asymmetric uplink: single-
   stream rclone fallback (8-way multipart stalled at ~220 KiB/s — which also
   slows the Browsertrix image pull), resumable + retried, sha256 after landing
   (3-copy rule: origin + local master + R2).
4. **Bounded memory** — stream verification; a whole-file `gzip.decompress`
   OOM-killed a 2.7 GB WACZ.
5. **Sensitive-data hygiene** — strip cookies/credentials before any public copy.
6. **Replay robustness** — vendored ReplayWeb (CDN blocked by injected CSP),
   HTTP range + CORS, a full-screen fallback link.

## Trust boundary / policy (#43)

- **Public / unauthenticated** → cloud on demand (#41/#42) for Tier 0; local
  real-browser for Tier 1. Shareable copies to the public R2 mirror.
- **Authenticated / cookie-bearing** (BoomheadNews and anything with a session)
  → **local on demand only** (run by hand, not a service), **private `shko`
  bucket only**, cookies **never** on shared edge. Datacenter IPs would get the
  account challenged/locked and are bot-walled anyway. Sanitize before any
  public copy. Overriding this is a conscious, case-by-case decision.

## R2 layout

- `shko` (private): WACZ masters, authenticated/sensitive captures, full-res
  screenshots, provenance manifests.
- `shko-public` → `pub-*.r2.dev` (→ eventually `archive.savehkonline.org`):
  shareable cold copies + cookie-sanitized WACZ only.

## The glue (#40)

A small capture-API Worker: `POST {url, mode}` → route (Browser Run screenshot /
Browsertrix WACZ / defer-to-local for authenticated) → right R2 bucket →
provenance record. `capture_refs.py` calls it instead of running captures
locally. The connector available in-session (Workers *Bindings* MCP) can manage
buckets but **cannot deploy Worker code / containers / Browser Run** — deploy
needs `wrangler` + a scoped token, or the newer `mcp.cloudflare.com/mcp`.

## Status (2026-11-10)

- ✅ `capture_page.py` built + dogfooded (ok/blocked/dead verified on
  hkfp/hkja/neodem).
- ✅ `capture_refs.py` built + dogfooded (#36): 6/6 real Joshua Wong citations
  (HKFP/AlJazeera/RFA/CNN/Wikimedia) captured ok, 0 false blocks.
- ✅ 3 Tier-0 screenshots captured + published (HKFP, PORI, Photon Media).
- ✅ **Browser Run worker (#41) — DEPLOYED LIVE** at
  `https://shko-capture-api.isaac-mao.workers.dev` (bindings: Browser Run +
  R2 `shko-public`; account on Workers Paid). End-to-end tested 2026-11-10:
  HKFP → `ok`, stored and retrievable from the public mirror; hkja → `blocked`
  (Cloudflare challenge caught, HTTP 422, nothing stored) — the edge enforces
  the same discipline as local. Deployed via `wrangler` OAuth (the browser
  callback was completed by delivering the localhost redirect to the server on
  the box, since the login runs headless here).
- ⏳ Browsertrix container (#42): scaffold committed; container image build/push
  + Cloudflare Container deploy is the remaining follow-up. Local `docker run`
  is the working equivalent.
- 🔗 Next wiring: point `capture_refs.py` at the deployed worker for Tier-0
  URLs (keep the local path as the Tier-1 fallback).
- ⛔ The Witness fresh WACZ: **crawl blocked**. Both a fast (3-worker) and a
  polite (1-worker, 8 s delays) crawl from this box's IP were rate-limited —
  1 page of 40–56, the rest HTTP 403 (195 403s in the polite run). The seed
  homepage loads but sustained crawling is walled. **Neither WACZ uploaded**
  (don't-store-a-failed-capture); the 2022 backup + Wayback stand. The Witness
  is a **Tier-1 crawl-blocked** site — needs a residential-IP vantage / rotating
  proxy, or rely on Wayback. Single-page cold-copy (`capture_page.py`) still
  works for it; whole-site WACZ does not from here.
