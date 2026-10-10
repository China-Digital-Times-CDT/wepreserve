#!/usr/bin/env bash
#
# Build a PUBLIC-SAFE copy of a WACZ by stripping request/response cookies
# (and Authorization) from every WARC record, then rebuilding the WACZ so its
# CDXJ index and datapackage hashes are regenerated cleanly.
#
# The cookie-bearing ORIGINAL is never modified. Verify + replay-test the
# output before publishing it anywhere public.
#
# Requires python3. Creates a throwaway venv with warcio + wacz on first run.
#
# Usage: scripts/wacz-strip-cookies.sh INPUT.wacz OUTPUT.wacz
set -euo pipefail

IN="${1:?usage: wacz-strip-cookies.sh INPUT.wacz OUTPUT.wacz}"
OUT="${2:?usage: wacz-strip-cookies.sh INPUT.wacz OUTPUT.wacz}"
[ -f "$IN" ] || { echo "ERROR: input $IN not found" >&2; exit 2; }

VENV="${VENV:-$HOME/.venv-wacz}"
if [ ! -x "$VENV/bin/wacz" ]; then
  echo "== setting up venv ($VENV) with warcio + wacz =="
  python3 -m venv "$VENV"
  "$VENV/bin/pip" -q install --upgrade pip
  "$VENV/bin/pip" -q install warcio wacz
fi
PY="$VENV/bin/python"; WACZ="$VENV/bin/wacz"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "== 1. extract $IN =="
"$PY" - "$IN" "$WORK" <<'PY'
import sys, zipfile
inp, work = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(inp) as z:
    z.extractall(work)
PY

echo "== 2. strip Cookie / Set-Cookie / Authorization from WARC records =="
mkdir -p "$WORK/clean"
"$PY" - "$WORK" <<'PY'
import sys, glob, os
from warcio.archiveiterator import ArchiveIterator
from warcio.warcwriter import WARCWriter
work = sys.argv[1]
STRIP = {"cookie", "set-cookie", "authorization"}
warcs = sorted(glob.glob(os.path.join(work, "archive", "*.warc.gz")) +
               glob.glob(os.path.join(work, "archive", "*.warc")))
assert warcs, "no WARCs found under archive/"
for w in warcs:
    base = os.path.basename(w)
    if not base.endswith(".gz"):
        base += ".gz"
    out = os.path.join(work, "clean", base)
    with open(w, "rb") as fi, open(out, "wb") as fo:
        writer = WARCWriter(fo, gzip=True)
        for rec in ArchiveIterator(fi):
            h = rec.http_headers
            if h is not None:
                h.headers = [(k, v) for (k, v) in h.headers
                             if k.lower() not in STRIP]
            # drop stale digests so they don't mismatch the edited block
            for dh in ("WARC-Block-Digest", "WARC-Payload-Digest"):
                try:
                    rec.rec_headers.remove_header(dh)
                except Exception:
                    pass
            writer.write_record(rec)
    print("  cleaned", base)
PY

echo "== 3. rebuild WACZ -> $OUT =="
PAGES_ARG=()
if [ -f "$WORK/pages/pages.jsonl" ]; then
  PAGES_ARG=(--pages "$WORK/pages/pages.jsonl")
  [ -f "$WORK/pages/extraPages.jsonl" ] && PAGES_ARG+=(--extra-pages "$WORK/pages/extraPages.jsonl")
else
  PAGES_ARG=(--detect-pages)
fi
"$WACZ" create -o "$OUT" -f "$WORK"/clean/*.warc.gz "${PAGES_ARG[@]}"

echo "== 4. verify no cookie headers remain in $OUT (streaming, low-memory) =="
"$PY" - "$OUT" <<'PY'
import sys, zipfile
from warcio.archiveiterator import ArchiveIterator
out = sys.argv[1]; bad = 0; recs = 0; warcs = 0
with zipfile.ZipFile(out) as z:
    for n in z.namelist():
        if n.endswith(".warc.gz"):
            warcs += 1
            with z.open(n) as f:                 # streamed; never loads whole member
                for rec in ArchiveIterator(f):
                    recs += 1
                    h = rec.http_headers
                    if h:
                        for k, v in h.headers:
                            if k.lower() in ("cookie", "set-cookie", "authorization"):
                                bad += 1
                                print("  STILL PRESENT:", k, "in", n)
print(f"  warcs={warcs} records={recs} remaining_cookie_headers={bad}")
sys.exit(1 if bad else 0)
PY
echo "CLEAN - no cookie headers remain."

echo "== 5. sizes =="; du -h "$IN" "$OUT"
echo "DONE -> $OUT  (replay-test it before publishing)"
