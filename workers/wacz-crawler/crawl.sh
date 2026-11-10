#!/usr/bin/env bash
# Env-driven one-shot crawl (#42). Required: SEED_URL. Optional: SCOPE, LIMIT,
# WORKERS, PAGE_TIMEOUT, COLLECTION. R2 upload happens automatically when the
# STORE_* env vars are set (see README) and --generateWACZ is on; Browsertrix
# only uploads WACZ output, not WARC.
set -euo pipefail

: "${SEED_URL:?set SEED_URL to the site to crawl}"

# Derive a collection name from the host + date if not given.
if [ -z "${COLLECTION:-}" ]; then
  host="$(printf '%s' "$SEED_URL" | sed -E 's#^https?://(www\.)?##; s#[/:].*$##')"
  COLLECTION="$(printf '%s' "$host" | sed -E 's#[^a-zA-Z0-9]+#-#g')-$(date +%Y%m%d)"
fi

echo "crawl: seed=$SEED_URL scope=${SCOPE:-prefix} limit=${LIMIT:-500} collection=$COLLECTION"

exec crawl \
  --seeds "$SEED_URL" \
  --scopeType "${SCOPE:-prefix}" \
  --limit "${LIMIT:-500}" \
  --workers "${WORKERS:-3}" \
  --pageLoadTimeout "${PAGE_TIMEOUT:-60}" \
  --generateWACZ \
  --collection "$COLLECTION"
