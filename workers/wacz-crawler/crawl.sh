#!/usr/bin/env bash
# Env-driven one-shot crawl (#42). Required: SEED_URL.
# Optional: SCOPE, LIMIT, WORKERS, PAGE_TIMEOUT, PAGE_DELAY, COLLECTION,
#           PROXY_SERVER (e.g. socks5://ts-exit:1055 — a residential egress).
# R2 upload happens automatically when the STORE_* env vars are set (see README)
# and --generateWACZ is on; Browsertrix uploads WACZ output only, not WARC.
#
# PROXY_SERVER is the fix for bot-walled sites: route the crawl through a
# residential egress (a Tailscale exit node at home) so requests don't come from
# a flagged datacenter IP. See docker-compose.yml + README.
set -euo pipefail

: "${SEED_URL:?set SEED_URL to the site to crawl}"

# Derive a collection name from the host + date if not given.
if [ -z "${COLLECTION:-}" ]; then
  host="$(printf '%s' "$SEED_URL" | sed -E 's#^https?://(www\.)?##; s#[/:].*$##')"
  COLLECTION="$(printf '%s' "$host" | sed -E 's#[^a-zA-Z0-9]+#-#g')-$(date +%Y%m%d)"
fi

# Build the arg list; add --proxyServer only when a proxy is configured.
args=(
  --seeds "$SEED_URL"
  --scopeType "${SCOPE:-prefix}"
  --limit "${LIMIT:-300}"
  --workers "${WORKERS:-2}"
  --pageLoadTimeout "${PAGE_TIMEOUT:-60}"
  --pageExtraDelay "${PAGE_DELAY:-2}"
  --generateWACZ
  --collection "$COLLECTION"
)
if [ -n "${PROXY_SERVER:-}" ]; then
  # Wait for the proxy sidecar to be reachable before starting the crawl.
  phost="${PROXY_SERVER#*://}"; pport="${phost##*:}"; phost="${phost%%:*}"
  echo "waiting for proxy $phost:$pport ..."
  for _ in $(seq 1 60); do
    if (exec 3<>"/dev/tcp/$phost/$pport") 2>/dev/null; then exec 3>&- 3<&-; break; fi
    sleep 2
  done
  args+=(--proxyServer "$PROXY_SERVER")
  echo "crawl egress via proxy: $PROXY_SERVER"
fi

echo "crawl: seed=$SEED_URL scope=${SCOPE:-prefix} limit=${LIMIT:-300} collection=$COLLECTION"
exec crawl "${args[@]}"
