# On-demand WACZ crawler (#42)

Heavy, unauthenticated whole-site WACZ capture (Tier-0/1 cooperative sites),
packaged as a one-shot container so it can run on demand and idle to zero.
Browsertrix Crawler does the crawl with a real Chromium (so it gets through
walls that `403` plain HTTP) and **uploads the WACZ straight to R2** via its
built-in S3 support. See `reports/capture-pipeline.md`.

**Unauthenticated sites only.** Anything needing cookies stays on the local
path (#43) — never route credentials through this.

> ⚠️ **Host requirements — NOT mars.** A whole-site crawl (Chromium + the
> ~2.4 GB image + page memory) needs real RAM. **mars has only 7.6 GB and runs
> here.news production** — a real crawl there risks OOM-killing the box, so do
> not run one on it (a tiny bounded `--limit 20` test is the ceiling). Run
> crawls on a disposable host with 8–16 GB (a cloud VM): do the login-profile
> there too, then upload the WACZ to R2. boomheadhk's ~12 GB WACZ was rsync'd
> from its origin host, *not* crawled on mars. For a Cloudflare-walled site that
> we can't give a bigger host, the single-page cold copy + screenshots
> (`capture_stealth.py --profile`) is the archive instead of a WACZ.

## Local on-demand run (the path dogfooded 2026-11-10)

```
docker run --rm --shm-size=2g -v "$PWD/crawls":/crawls \
  webrecorder/browsertrix-crawler:latest crawl \
  --seeds https://thewitnesshk.com/ --scopeType prefix --limit 120 \
  --workers 3 --generateWACZ --collection thewitness-2026-11-10
# -> crawls/collections/thewitness-2026-11-10/thewitness-2026-11-10.wacz
```

This image wraps that in an env-driven entrypoint (`crawl.sh`): set `SEED_URL`
(and optionally `SCOPE`, `LIMIT`, `WORKERS`, `PAGE_TIMEOUT`, `COLLECTION`).

## Stream the WACZ to R2 (built-in S3 upload)

Set these env vars and Browsertrix uploads the WACZ on success (WACZ output
only — not WARC). R2 is S3-compatible:

| env | value |
|---|---|
| `STORE_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com/shko/` (bucket + trailing slash) |
| `STORE_ACCESS_KEY` | R2 S3 access key id (32 hex) |
| `STORE_SECRET_KEY` | R2 S3 secret (64 hex) |
| `STORE_PATH` | key prefix, e.g. `wacz/thewitness/` |
| `STORE_FILENAME` | e.g. `@id-@ts.wacz` |

> Verify these exact names against the current Browsertrix docs before relying
> on them — the upload client moved to AWS SDK multipart and the var names have
> shifted across releases. Keep the single-stream / thin-pipe caveat from
> `reports/capture-pipeline.md` in mind for big WACZ.

After upload, sha256-verify and record provenance (3-copy rule), then repoint
the site's `sites.*` page from any stale backup to the fresh capture, replayed
via the self-hosted ReplayWeb path (#26).

## The egress problem — and the decision tree (measured, not assumed)

**mars is itself on a home/residential line** (public IP `72.136.97.2`), so the
first question is never "datacenter vs residential" — mars already has a clean
residential egress. The real split is whether the *target* bot-walls that
specific IP:

1. **Cooperative / unwalled sites → crawl directly from mars. No proxy.**
   Measured 2026-11-12: a direct Browsertrix crawl of `photonmedia.net` from
   mars captured **20/20 pages, 0 failed, 0 excluded → valid 58 MB WACZ**. For
   these sites the Tailscale sidecar below is unnecessary overhead — just run
   the plain `docker run` from the "Local on-demand run" section, or
   `docker compose` with `PROXY_SERVER` left unset.

2. **Sites that wall mars's own residential IP → need a *different* clean line.**
   Proven walls: The Witness gave 1 page then `403` at scale; hkja serves a
   Cloudflare *managed challenge* that **no IP clears** — even the Internet
   Archive crawler is `403`'d on it. A **Cloudflare Container is a datacenter
   IP**, strictly worse, so that path is abandoned. A Tailscale exit node only
   helps here if it is a *genuinely different, cleaner* residential line (e.g. a
   phone on cellular, or a Pi at another location) — routing through a second
   home line that is also flagged, or through mars itself, buys nothing. For a
   hard managed-challenge site (hkja) even that may not win; fall back to
   single-page screenshots (#44) + full-text (#36).

For case 2, change *where the requests come out*, not where the compute runs:
route the crawl through a **Tailscale exit node on a different residential
connection**. `docker-compose.yml` runs the crawl on mars but sends its browser
traffic through a userspace-Tailscale **SOCKS5 proxy** pinned to that exit node.
The WACZ upload to R2 still goes out mars's normal route.

### One-time setup

1. **Home exit node.** On an always-on device at home (Pi / NAS / old laptop —
   on residential internet, *not* mars):
   ```
   tailscale up --advertise-exit-node
   ```
   Then approve it in the admin console (Machines → that device → Edit route
   settings → "Use as exit node"). Confirm from mars: `tailscale exit-node list`
   should now list it. (The tailnet already has `mars`, but mars's own
   residential IP is the one being walled in case 2 — so the exit node must be a
   *different* line, e.g. a phone on cellular or a Pi elsewhere, not mars.)
2. **Auth key.** Create a reusable/ephemeral key at
   `login.tailscale.com/admin/settings/keys` for the sidecar.
3. **R2 S3 creds** (optional, for direct upload) — an R2 API token with object
   write on the target bucket.

Put all three + `SEED_URL` in a `.env` (copy `.env.example`; `.env` is
gitignored).

### Run a crawl (on mars)

```
cd workers/wacz-crawler
cp .env.example .env     # fill in TS_AUTHKEY, TS_EXIT_NODE, SEED_URL, (STORE_*)
SEED_URL=https://thewitnesshk.com/ docker compose --env-file .env up \
    --build --abort-on-container-exit --exit-code-from crawler
docker compose down      # tear down the sidecar
```

Verify the egress is residential before trusting a crawl: the sidecar's SOCKS5
is on `ts-exit:1055`; a quick check —
`docker compose run --rm crawler bash -lc 'curl -s --socks5-hostname ts-exit:1055 https://api.ipify.org'`
should print a **home** IP, not mars's.

Keep `WORKERS` low and `PAGE_DELAY` ≥2 — you're crawling over a home uplink and
want to stay polite. WACZ output (thin mars uplink for the R2 upload) is a
single file; background it or use the local `./crawls` copy + `rclone`.

### Cloudflare Container (not used)

A Cloudflare Container would idle-to-zero nicely but shares the datacenter-IP
wall above, so it does not solve #42 for walled sites. Left here only to record
the decision. For *cooperative* sites a container crawl would work, but those we
already cover with single-page screenshots (#44) + full-text (#36).
