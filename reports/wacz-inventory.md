# WACZ archive inventory & migration tracker

Tracks web archives (WACZ) being consolidated onto the durable framework:
**local master + Cloudflare R2** (private `shko` for originals; public
`shko-public` for cookie-sanitized copies) **+ a replay page** on the site.
See `reports/README.md` sibling notes and the helper scripts in `scripts/`
(`r2-sync-wacz.sh`, `wacz-strip-cookies.sh`, `wacz-verify-nocookies.py`).

Goal: get every at-risk archive to **3 copies** (origin + local master + R2)
with a `sha256` recorded, before any single unreliable source is lost.

Status legend: 🔎 located · ⬇️ pulled to master · 🧼 sanitized (if needed) ·
☁️ in R2 · 📄 replay page repointed · ✅ done.

## Where the old WACZs actually live

Swept from the vault on 2026-10-10 (there are **no local WACZ copies**; every
old archive is remote and linked from a `sites.*` page). Two backends:

- **Google Cloud Storage** — bucket `web-archive-storage-sage-striker-294302`,
  path `/archives/`, served at `storage.googleapis.com/…`. All 8 objects
  **live** (HTTP 206, range-enabled) as of the sweep; **5.54 GB total**. This
  is a billed GCP project — the most likely "may lapse" risk, so migrate first.
- **IPFS** — `https://<cid>.ipfs.dweb.link/fixtures/<name>.wacz`. Content-addressed;
  survives only while the pin is paid/alive. Several captures share one CID
  (bundled in a single `fixtures/` directory), so they're a handful of CAR
  pins, not 10 independent ones. **Liveness unconfirmed:** public gateways
  (dweb.link, ipfs.io) returned `429 Too Many Requests` on every probe
  2026-10-10 — rate-limiting, which means "can't tell", not "dead". Confirm
  by resolving the CIDs from a local IPFS daemon or by checking the pinning
  service account (see open questions); do not assume they're gone.

All old captures are of **public sites** (news orgs, NGOs, a museum) — none
were crawled behind a login, so unlike `boomheadhk` they need **no
cookie-stripping**: verify sha256 → copy to R2 → repoint the replay link.

## Migration tracker

| Archive (page) | Backend / object | Size | Login cookies? | In R2 | Status |
|---|---|---|---|---|---|
| **boomheadhk** ([[Boom News\|sites.boomnews]]) | R2 + master `/media/im3/plus/lab/archive/boomheadhk-share/` | 2.7 GB (3 parts 5.5 GB) | **Yes** (FB session; stripped for public copy) | `shko/boomheadhk` (orig) + `shko-public/boomheadhk` (sanitized) | ✅ |
| factwire ([[sites.factwire]]) | GCS `factwire.wacz` | 215 MB | No | `shko-public/wacz/factwire.wacz` | ☁️ |
| guhkst ([[sites.guhkst]]) | GCS `guhkst-04_22_2022.wacz` | 235 MB | No | `shko-public/wacz/guhkst.wacz` | ☁️ |
| hkharborprotection ([[sites.hkharborprotection]]) | GCS `f364853e.wacz` | 369 MB | No | `shko-public/wacz/hkharborprotection.wacz` | ☁️ |
| hongkongwatch 2025 ([[sites.hongkongwatch]]) | GCS `72de847d.wacz` | 1.18 GB | No | `shko-public/wacz/hongkongwatch-2025.wacz` | ☁️ |
| photonmedia ([[sites.photonmedia]]) | GCS `3b628a67.wacz` | 760 MB | No | `shko-public/wacz/photonmedia.wacz` | ☁️ |
| rfa_cantonese ([[sites.rfa_cantonese]]) | GCS `996daaf7.wacz` | 1.04 GB | No | `shko-public/wacz/rfa_cantonese.wacz` | ☁️ |
| webb-site ([[sites.webb]]) | GCS `ddb492c7.wacz` | 442 MB | No | `shko-public/wacz/webb.wacz` | ☁️ |
| 8964museum ([[extra.8964]]) | GCS `8964museum-05_04_2022.wacz` **+ IPFS** `bafybeiaosx…` | 995 MB | No | `shko-public/wacz/8964museum.wacz` | ☁️ |
| appledaily ([[sites.appledaily]]) | IPFS `bafybeiheij…` `appledaily-05_23_2020.wacz` | n/a ¹ | No | — | 🔎 |
| passiontimes ([[sites.passiontimes]]) | IPFS `bafybeiheij…` `passiontime-05_23_2022.wacz` (same CID as appledaily) | n/a ¹ | No | — | 🔎 |
| hkfp ([[sites.hkfp]]) | IPFS `bafybeighmf…` `hkfp-05_03_2022.wacz` | n/a ¹ | No | — | 🔎 |
| inmediahk ([[sites.inmediahk]]) | IPFS `bafybeighmf…` `inmediahk-05_03_2022.wacz` (same CID as hkfp) | n/a ¹ | No | — | 🔎 |
| hongkongwatch 2022 ([[sites.hongkongwatch]]) | IPFS `bafybeihkns…` `hkwatch-05_03_2022.wacz` | n/a ¹ | No | — | 🔎 |
| lsd ([[sites.lsd]]) | IPFS `bafybeid553…` `lsd-05_24_2022.wacz` | n/a ¹ | No | — | 🔎 |
| thewitness ([[sites.thewitness]]) | IPFS `bafybeid553…` `thewitness-05_31_2022.wacz` (same CID as lsd) | n/a ¹ | No | — | 🔎 |
| pori ([[sites.pori]]) | IPFS `bafybeiae2d…` `pori-04_25_2022.wacz` | n/a ¹ | No | — | 🔎 |
| standnews ([[sites.standnews]]) | IPFS `bafybeibxk2…` `standnews-05_12_2022.wacz` | n/a ¹ | No | — | 🔎 |

¹ IPFS object size not captured: public gateways rate-limited (`429`) the
size probe on 2026-10-10. Record each via a local IPFS daemon or the pin
service when liveness is confirmed.

Not migration targets (external services we only *link*, not host): Wayback
Machine (`web.archive.org`) references on most `sites.*` pages — leave as-is.

## Proposed order
1. ✅ **GCS — DONE (2026-11-10).** All 8 objects (5.54 GB) copied to
   `r2:shko-public/wacz/<name>.wacz`, each **byte-exact** (Content-Length
   matched the source). Served at `https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/wacz/<name>.wacz`
   with `application/wacz`, range (206) and CORS `*` — ReplayWeb-ready.
   **Mechanism — server-side, no local bandwidth:** the `shko-capture-api`
   Worker gained a `mirror` endpoint (`POST {mirror:"<public-url>", key:"<r2-key>"}`,
   auth + SSRF-guarded) that streams a public URL straight into R2 inside
   Cloudflare's network — 5.5 GB moved in ~4 min vs ~7 h over the box's
   ~220 KiB/s uplink. GCS originals kept in place (don't delete until the
   replay links are repointed and a `sha256`/replay check is done).
   **Remaining:** repoint each `sites.*` page's `storage.googleapis.com/…` link
   to the R2 copy (ideally a vendored ReplayWeb viewer like `sites.boomnews`),
   then the GCS bucket can be retired.
2. **IPFS next** (lower urgency if pins hold): dedupe by CID (7 unique) so each
   CAR is pulled once; same verify → R2 → repoint.
3. Record a `sha256` per object as it lands. Keep GCS/IPFS originals in place
   until the R2 copy is verified (3-copy rule).

## Open questions
- **Billing deadline:** when is the GCP project / its bucket at risk? (drives GCS urgency)
- **Custom domain:** once `archive.savehkonline.org` resolves + R2 domain is
  connected, repoint links there instead of `pub-…r2.dev` (one pass over the
  pages, matching the boomnews TODO).
- **IPFS pins:** who holds them (web3.storage / Pinata / self)? If unknown and
  unpaid, treat IPFS as at-risk too and raise its priority.
