#!/usr/bin/env bash
#
# Monthly auto-capture for the time-series screenshot archive (issue #44).
#
# Runs on the box that holds the capture venv + rclone `r2` creds (mars) — the
# cloud audit routine CANNOT capture (no browser / R2 creds there), so the
# actual capture is a local cron here. Captures the curated non-residential
# targets, publishes dated snapshots + thumbnails to R2, and refreshes the
# public manifest. Residential-only targets (hkja) are skipped — run those by
# hand from a residential connection (see the issue).
#
# Install (1st of each month, 09:00 local):
#   ( crontab -l 2>/dev/null; \
#     echo '0 9 1 * * /media/im3/plus/lab/archive/wepreserve/scripts/screenshot_archive_cron.sh' \
#   ) | crontab -
#
set -euo pipefail
REPO="/media/im3/plus/lab/archive/wepreserve"
cd "$REPO"
LOG="$REPO/captures/shots/cron-$(date -u +%Y%m).log"
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) monthly screenshot-archive run ==="
xvfb-run -a "$REPO/.capture-venv/bin/python" "$REPO/scripts/screenshot_archive.py" \
  --capture --manifest --report

# Commit the refreshed manifest so the monthly cloud audit routine (which can't
# reach R2 from its sandbox) reads current freshness from the checkout. Stage
# ONLY this file — never `git add -A`.
if ! git -C "$REPO" diff --quiet -- reports/screenshot-index.json 2>/dev/null; then
  git -C "$REPO" add reports/screenshot-index.json
  git -C "$REPO" commit -q -m "screenshot-archive: refresh manifest ($(date -u +%Y-%m))" \
    && git -C "$REPO" push -q origin main \
    && echo "manifest committed + pushed"
fi
echo "=== done $(date -u +%FT%TZ) ==="
