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

## Cloudflare Container deploy (on demand)

Build/push this image as a Cloudflare Container (GA Apr 2026) and trigger it
from the capture-API Worker (`workers/capture-api`). The container wrapper
(wrangler `[[containers]]` + a Durable Object router) is deploy-specific —
confirm the current Containers binding API against Cloudflare's docs, and pass
`SEED_URL` + the `STORE_*` secrets to the instance. Live deploy is gated on a
deploy path (scoped wrangler token or `mcp.cloudflare.com/mcp`); the local
`docker run` above is the working equivalent meanwhile.
