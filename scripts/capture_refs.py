#!/usr/bin/env python3
"""
capture_refs.py — cold-capture the archive's reference URLs (#36).

Walks the vault's markdown, pulls out the external citation URLs, and runs each
through capture_page.capture() to produce a durable cold copy (screenshot + DOM)
plus a provenance record — so that if a cited page disappears, we still hold a
dated, hash-verified copy. Built on the same block/challenge detection, so dead
or bot-walled references are *flagged* in the manifest rather than silently
stored as if captured.

This is the engine the #40 capture-API Worker will call in the cloud; locally it
is the Tier-1 / residential backbone (and the thing that lets us honour "cold
copy of every reference URL we cite").

Usage:
    # sample one page, a few refs:
    python3 scripts/capture_refs.py --path vault/sites.hkja.md --limit 5 --out captures
    # whole vault (big, slow — dead/blocked refs take ~90s each):
    python3 scripts/capture_refs.py --out captures --manifest captures/manifest.json

Hosts we only *link* (Wayback, IPFS, our own R2/site, GitHub, library/cover
lookups, video, Wikipedia) are skipped — we don't cold-copy infrastructure.
"""
import argparse
import csv
import datetime as _dt
import glob
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture_page  # noqa: E402  (sibling script)

URL_RE = re.compile(r'https?://[^\s<>()\[\]"\\]+')

# Hosts we deliberately do not cold-copy: archival infra, our own storage/site,
# code hosting, and lookup/video/reference services that are not "sources".
SKIP_HOSTS = (
    "web.archive.org", "archive.org", "ipfs.dweb.link", "ipfs.io", ".r2.dev",
    "storage.googleapis.com", "github.com", "githubusercontent.com",
    "savehkonline.org", "replayweb.page", "openlibrary.org",
    "covers.openlibrary.org", "youtube.com", "youtu.be", "vimeo.com",
    "zh.wikipedia.org", "en.wikipedia.org", "wikipedia.org",
)


def _clean(u):
    # strip markdown/sentence trailing punctuation
    return u.rstrip('.,;:!?)]}"\'>')


def _host(u):
    return u.split("//", 1)[-1].split("/", 1)[0].lower()


def collect(paths):
    """url -> first vault file it appears in (insertion order preserved)."""
    found = {}
    for p in sorted(paths):
        try:
            txt = open(p, encoding="utf-8").read()
        except OSError:
            continue
        for m in URL_RE.findall(txt):
            u = _clean(m)
            if not u or any(s in _host(u) for s in SKIP_HOSTS):
                continue
            found.setdefault(u, os.path.relpath(p))
    return found


def name_for(u):
    host = re.sub(r"^www\.", "", _host(u))
    tag = hashlib.sha1(u.encode("utf-8")).hexdigest()[:8]
    return re.sub(r"[^a-z0-9.-]+", "-", host).strip("-") + "-" + tag


def main(argv):
    ap = argparse.ArgumentParser(description="Cold-capture archive reference URLs (#36).")
    ap.add_argument("--path", action="append",
                    help="specific markdown file(s); default: all of vault/*.md")
    ap.add_argument("--out", default="captures", help="output directory")
    ap.add_argument("--limit", type=int, default=0, help="cap number of refs (0 = all)")
    ap.add_argument("--manifest", help="write/update a JSON manifest here")
    ap.add_argument("--force", action="store_true",
                    help="re-capture even if an ok provenance JSON already exists")
    a = ap.parse_args(argv)

    paths = a.path or glob.glob("vault/*.md")
    refs = collect(paths)
    items = list(refs.items())
    if a.limit:
        items = items[:a.limit]

    os.makedirs(a.out, exist_ok=True)
    rows = []
    counts = {"ok": 0, "blocked": 0, "dead": 0, "skipped": 0}
    for i, (url, src) in enumerate(items, 1):
        name = name_for(url)
        meta = os.path.join(a.out, name + ".json")
        if os.path.exists(meta) and not a.force:
            try:
                prev = json.load(open(meta))
                if prev.get("status") == "ok":
                    counts["skipped"] += 1
                    print(f"[{i}/{len(items)}] · skip (already ok) {url}")
                    rec = prev
                    rec["source"] = src
                    rows.append(rec)
                    continue
            except (OSError, ValueError):
                pass
        print(f"[{i}/{len(items)}] capturing {url}")
        rec = capture_page.capture(url, a.out, name)
        rec["source"] = src
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        rows.append(rec)

    manifest = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "counts": counts,
        "total": len(rows),
        "captures": rows,
    }
    if a.manifest:
        with open(a.manifest, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("\n=== reference-capture summary ===")
    print(f"refs seen: {len(refs)}  processed: {len(items)}")
    print(f"ok={counts['ok']}  blocked={counts['blocked']}  "
          f"dead={counts['dead']}  skipped(already ok)={counts['skipped']}")
    if a.manifest:
        print(f"manifest: {a.manifest}")
    # non-zero exit if anything needs a human (blocked/dead), per the
    # don't-silently-lose-a-reference discipline.
    return 0 if (counts["blocked"] == 0 and counts["dead"] == 0) else 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
