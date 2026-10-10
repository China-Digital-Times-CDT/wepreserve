#!/usr/bin/env bash
#
# Verify a WACZ share's checksums and sync it to the Cloudflare R2 "shko"
# bucket. Credentials are read from the environment (never hard-coded, never
# committed). rclone must be on PATH (installed at ~/bin/rclone).
#
# Required env vars (from an R2 API token, "Object Read & Write" on bucket shko):
#   R2_ACCOUNT_ID         Cloudflare account id
#   R2_ACCESS_KEY_ID      R2 access key id
#   R2_SECRET_ACCESS_KEY  R2 secret access key
# Optional:
#   SRC   source dir (default: /media/im3/plus/lab/archive/boomheadhk-share)
#   DEST  bucket/prefix (default: shko/boomheadhk)
#   BUCKET  bucket name (default: shko)
#
# Usage:  R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
#         scripts/r2-sync-wacz.sh
set -euo pipefail

SRC="${SRC:-/media/im3/plus/lab/archive/boomheadhk-share}"
BUCKET="${BUCKET:-shko}"
DEST="${DEST:-$BUCKET/boomheadhk}"
RCLONE="$(command -v rclone || echo "$HOME/bin/rclone")"

for v in R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY; do
  [ -n "${!v:-}" ] || { echo "ERROR: env var $v is not set" >&2; exit 2; }
done
[ -d "$SRC" ] || { echo "ERROR: source dir $SRC not found" >&2; exit 2; }

echo "== 1. Verify checksums in $SRC =="
if [ -f "$SRC/SHA256SUMS-single" ]; then
  ( cd "$SRC" && sha256sum -c SHA256SUMS-single )
else
  echo "WARN: no SHA256SUMS-single found; computing a manifest instead"
fi

echo "== 2. Write a durable manifest (name, bytes, sha256) =="
MAN="$SRC/MANIFEST-wacz.txt"
: > "$MAN"
while IFS= read -r -d '' f; do
  sz=$(stat -c%s "$f"); sum=$(sha256sum "$f" | cut -d' ' -f1)
  printf '%s  %s  %s\n' "$(basename "$f")" "$sz" "$sum" | tee -a "$MAN"
done < <(find "$SRC" -maxdepth 1 -name '*.wacz' -print0 | sort -z)
echo "manifest -> $MAN"

echo "== 3. Configure rclone R2 remote (600-perm, from env) =="
CONF_DIR="$HOME/.config/rclone"; mkdir -p "$CONF_DIR"; CONF="$CONF_DIR/rclone.conf"
touch "$CONF"; chmod 600 "$CONF"
# (re)write only the [r2] stanza
"$RCLONE" config delete r2 >/dev/null 2>&1 || true
cat >> "$CONF" <<EOF
[r2]
type = s3
provider = Cloudflare
access_key_id = ${R2_ACCESS_KEY_ID}
secret_access_key = ${R2_SECRET_ACCESS_KEY}
endpoint = https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com
acl = private
no_check_bucket = true
EOF

echo "== 4. Upload *.wacz (content-type application/wacz) =="
"$RCLONE" copy "$SRC" "r2:$DEST" \
  --include '*.wacz' \
  --header-upload "Content-Type: application/wacz" \
  --s3-no-head --progress --transfers 2 --checkers 4

echo "== 5. Upload sidecars (readmes + checksums + manifest) =="
"$RCLONE" copy "$SRC" "r2:$DEST" \
  --include '*.txt' --include 'SHA256SUMS*' \
  --progress --transfers 2

echo "== 6. Listing on R2 =="
"$RCLONE" ls "r2:$DEST"
echo "DONE. Objects are under r2:$DEST (bucket $BUCKET)."
