# On-demand WACZ crawler (#42)

Heavy, unauthenticated whole-site WACZ capture (Tier-0/1 cooperative sites),
packaged as a one-shot container so it can run on demand and idle to zero.
Browsertrix Crawler does the crawl with a real Chromium (so it gets through
walls that `403` plain HTTP) and **uploads the WACZ straight to R2** via its
built-in S3 support. See `reports/capture-pipeline.md`.

**Unauthenticated sites only.** Anything needing cookies stays on the local
path (#43) — never route credentials through this.

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

## The egress problem, and the fix (residential Tailscale exit node)

Whole-site crawling of bot-walled sites **cannot be done from a datacenter IP**
— proven repeatedly: The Witness crawl got 1 page then `403` at scale from mars;
hkja serves a Cloudflare *managed challenge* no server IP clears; even the
Internet Archive crawler is `403`'d on hkja. A **Cloudflare Container is also a
datacenter IP**, so it hits the same wall — that path is abandoned.

The fix is to change *where the requests come out*, not where the compute runs:
route the crawl through a **Tailscale exit node on a home/residential
connection**. `docker-compose.yml` runs the crawl on mars but sends its browser
traffic through a userspace-Tailscale **SOCKS5 proxy** pinned to that exit node,
so requests leave from a residential IP. The WACZ upload to R2 still goes out
mars's normal route.

### One-time setup

1. **Home exit node.** On an always-on device at home (Pi / NAS / old laptop —
   on residential internet, *not* mars):
   ```
   tailscale up --advertise-exit-node
   ```
   Then approve it in the admin console (Machines → that device → Edit route
   settings → "Use as exit node"). Confirm from mars: `tailscale exit-node list`
   should now list it. (The tailnet already has `mars`; it just needs a
   residential node — mars itself can't be the exit, it's the datacenter IP
   we're avoiding.)
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
