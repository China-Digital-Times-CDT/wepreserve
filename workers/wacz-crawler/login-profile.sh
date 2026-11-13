#!/usr/bin/env bash
# Interactive Browsertrix login-profile creation (#42), for whole-site crawls of
# sites behind a login OR a Cloudflare managed challenge (e.g. hkja.org.hk).
#
# You solve the challenge ONCE in Browsertrix's own browser; it saves a
# profile .tar.gz carrying the matching user-agent + cf_clearance cookie, which
# the crawl then reuses (PROFILE=... crawl.sh, or `crawl --profile ...`) so every
# page loads clean instead of hitting the interstitial. cf_clearance is bound to
# the browser identity, which is why it must be *Browsertrix's* browser that
# clears it, not your desktop Chrome.
#
# Usage:
#   ./login-profile.sh https://hkja.org.hk/ [out-name]
#
# Then, on mars's desktop (or through an SSH tunnel: `ssh -L 9223:localhost:9223
# im@mars`), open http://localhost:9223/ , drive the embedded browser to the
# site, wait out / solve the challenge until the REAL page renders, then click
# "Create Profile". The <out-name>.tar.gz lands in ./crawls/profiles/.
set -euo pipefail

URL="${1:?usage: login-profile.sh <url> [out-name]}"
NAME="${2:-$(printf '%s' "$URL" | sed -E 's#^https?://(www\.)?##; s#[/:].*##; s#[^a-zA-Z0-9]+#-#g')}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/crawls/profiles"

echo "Creating login profile for: $URL"
echo "  -> open http://localhost:9223/  (mars desktop, or tunnel port 9223)"
echo "  -> solve the challenge until the real page shows, then click 'Create Profile'"
echo "  -> result: $HERE/crawls/profiles/$NAME.tar.gz"
exec docker run --rm -p 9223:9223 -p 6080:6080 \
  -v "$HERE/crawls/profiles":/crawls/profiles \
  -it webrecorder/browsertrix-crawler:latest \
  create-login-profile --url "$URL" --filename "/crawls/profiles/$NAME.tar.gz"
