#!/usr/bin/env python3
"""Verify a WACZ has NO Cookie / Set-Cookie / Authorization headers in any
WARC record. Streams each record (low memory) — safe on multi-GB archives.

Usage:  ~/.venv-wacz/bin/python scripts/wacz-verify-nocookies.py FILE.wacz
Exit 0 = clean, 1 = headers still present, 2 = usage error.
"""
import sys
import zipfile
from warcio.archiveiterator import ArchiveIterator

if len(sys.argv) != 2:
    print("usage: wacz-verify-nocookies.py FILE.wacz", file=sys.stderr)
    sys.exit(2)

out = sys.argv[1]
BAD = {"cookie", "set-cookie", "authorization"}
bad = recs = warcs = 0
with zipfile.ZipFile(out) as z:
    for n in z.namelist():
        if n.endswith(".warc.gz"):
            warcs += 1
            with z.open(n) as f:                 # streamed; never loads whole member
                for rec in ArchiveIterator(f):
                    recs += 1
                    h = rec.http_headers
                    if h:
                        for k, _v in h.headers:
                            if k.lower() in BAD:
                                bad += 1
                                print(f"  STILL PRESENT: {k} in {n}")
print(f"warcs={warcs} records={recs} remaining_cookie_headers={bad}")
sys.exit(1 if bad else 0)
