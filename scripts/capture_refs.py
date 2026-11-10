#!/usr/bin/env python3
"""
capture_refs.py — cold-capture the archive's reference URLs (#36).

Walks the vault's markdown, pulls out the external citation URLs, and captures
each one so that if a cited page disappears, we still hold a dated, hash-verified
copy. Two engines:

  * local (default) — render in a real headless Chrome via capture_page.py;
    artifacts + provenance written under --out.
  * edge  (--worker) — POST each URL to the deployed Browser Run worker (#41),
    which stores the screenshot/HTML/provenance to R2. Offloads Tier-0 work to
    the cloud; with --fallback-local, a URL the edge can't get (e.g. a site that
    bot-walls Cloudflare IPs) is retried on the local real-browser path.

Both engines use the same block/challenge classification, so dead or bot-walled
references are flagged in the manifest (ok/blocked/dead/error), never silently
stored as if captured.

Usage:
    # local, sample one page:
    python3 scripts/capture_refs.py --path vault/sites.hkja.md --limit 5 --out captures
    # via the live edge worker, with local fallback, whole vault:
    python3 scripts/capture_refs.py --worker --fallback-local \
        --manifest captures/manifest.json

Hosts we only *link* (Wayback, IPFS, our own R2/site, GitHub, library/cover
lookups, video, Wikipedia) are skipped — we don't cold-copy infrastructure.
"""
import argparse
import datetime as _dt
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture_page  # noqa: E402  (sibling script)
# fetch_extract imports curl_cffi/trafilatura lazily (only when its capture runs),
# so importing the module here is cheap and safe outside the capture venv.
import fetch_extract  # noqa: E402  (sibling script — the Tier-1 text engine)

URL_RE = re.compile(r'https?://[^\s<>()\[\]"\\]+')

DEFAULT_WORKER = "https://shko-capture-api.isaac-mao.workers.dev/"
DEFAULT_TOKEN_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "workers", "capture-api", ".capture-token")

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


def _worker_once(worker_url, token, url, name, timeout):
    data = json.dumps({"url": url, "name": name}).encode("utf-8")
    req = urllib.request.Request(
        worker_url, data=data, method="POST",
        headers={"content-type": "application/json", "x-capture-token": token,
                 # Cloudflare's bot filter 403s the default Python-urllib UA
                 # before the request reaches the Worker — identify ourselves.
                 "user-agent": "shko-capture-refs/0.1 (+https://savehkonline.org)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8")), e.code
        except Exception:
            return {"status": "error", "note": f"HTTP {e.code}"}, e.code
    except Exception as e:  # network / timeout
        return {"status": "error", "note": str(e)}, 0


def worker_capture(worker_url, token, url, name, timeout=100, retries=2, backoff=5):
    """Capture via the deployed Browser Run worker (Tier-0 edge; artifacts land
    in R2, not local disk). Retries transient edge/Browser-Run failures (5xx /
    network) with backoff; does not retry a real ok/blocked/dead verdict.
    Returns a provenance dict with engine='edge'."""
    rec = {"status": "error", "note": "not attempted"}
    for attempt in range(retries + 1):
        rec, code = _worker_once(worker_url, token, url, name, timeout)
        transient = code in (0, 429, 500, 502, 503)
        if rec.get("status") == "error" and transient and attempt < retries:
            time.sleep(backoff * (attempt + 1))
            continue
        break
    rec.setdefault("url", url)
    rec.setdefault("status", "error")
    rec["engine"] = "edge"
    return rec


def main(argv):
    ap = argparse.ArgumentParser(description="Cold-capture archive reference URLs (#36).")
    ap.add_argument("--path", action="append",
                    help="specific markdown file(s); default: all of vault/*.md")
    ap.add_argument("--out", default="captures", help="output directory (local engine)")
    ap.add_argument("--limit", type=int, default=0, help="cap number of refs (0 = all)")
    ap.add_argument("--manifest", help="write a JSON manifest here")
    ap.add_argument("--force", action="store_true",
                    help="re-capture even if an ok provenance JSON already exists (local)")
    ap.add_argument("--text", action="store_true",
                    help="use the Tier-1 full-text engine (fetch_extract: "
                         "curl_cffi + trafilatura) instead of a screenshot — "
                         "captures clean article text + raw HTML. Run with the "
                         "capture venv's python (curl_cffi/trafilatura).")
    ap.add_argument("--r2", action="store_true",
                    help="with --text, upload each clean capture to the public "
                         "mirror (r2:shko-public/fulltext/...). Public pages only.")
    ap.add_argument("--worker", nargs="?", const=DEFAULT_WORKER, default=None,
                    metavar="URL",
                    help="capture via the edge Browser Run worker (Tier-0); "
                         "optional URL overrides the default")
    ap.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                    help="file holding the worker's x-capture-token")
    ap.add_argument("--fallback-local", action="store_true",
                    help="if the edge returns non-ok (e.g. Cloudflare-blocked), "
                         "retry the URL on the local real-browser path")
    ap.add_argument("--delay", type=float, default=2.0,
                    help="seconds between edge requests (respects Browser Run's "
                         "new-instance rate; edge engine only)")
    a = ap.parse_args(argv)

    if a.text and a.worker:
        sys.exit("capture_refs: --text and --worker are different engines; pick one")
    if a.r2 and not a.text:
        sys.exit("capture_refs: --r2 uploads text captures; it needs --text")

    token = ""
    if a.worker:
        try:
            token = open(a.token_file).read().strip()
        except OSError:
            sys.exit(f"capture_refs: cannot read token file {a.token_file}")
        if not token:
            sys.exit(f"capture_refs: empty token in {a.token_file}")

    paths = a.path or glob.glob("vault/*.md")
    refs = collect(paths)
    items = list(refs.items())
    if a.limit:
        items = items[:a.limit]

    os.makedirs(a.out, exist_ok=True)
    rows = []
    counts = {"ok": 0, "blocked": 0, "dead": 0, "error": 0, "skipped": 0}
    for i, (url, src) in enumerate(items, 1):
        name = name_for(url)
        meta = os.path.join(a.out, name + ".json")
        if not a.worker and os.path.exists(meta) and not a.force:
            try:
                prev = json.load(open(meta))
                if prev.get("status") == "ok":
                    counts["skipped"] += 1
                    print(f"[{i}/{len(items)}] · skip (already ok) {url}")
                    prev["source"] = src
                    rows.append(prev)
                    continue
            except (OSError, ValueError):
                pass

        if a.text:
            print(f"[{i}/{len(items)}] text  {url}")
            rec = fetch_extract.capture_to_dir(url, a.out, name, do_r2=a.r2)
            rec.pop("_json_path", None)  # local path, not for the manifest
            rec["engine"] = "text"
        elif a.worker:
            if i > 1 and a.delay > 0:
                time.sleep(a.delay)
            print(f"[{i}/{len(items)}] edge  {url}")
            rec = worker_capture(a.worker, token, url, name)
            if rec.get("status") != "ok" and a.fallback_local:
                edge_status = rec.get("status")
                print(f"           edge={edge_status} -> local fallback")
                rec = capture_page.capture(url, a.out, name)
                rec["engine"] = "local"
                rec["edge_first"] = edge_status
        else:
            print(f"[{i}/{len(items)}] local {url}")
            rec = capture_page.capture(url, a.out, name)
            rec["engine"] = "local"

        rec["source"] = src
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        rows.append(rec)

    engine_label = "text" if a.text else ("edge" if a.worker else "local")
    manifest = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "engine": engine_label,
        "counts": counts,
        "total": len(rows),
        "captures": rows,
    }
    if a.manifest:
        with open(a.manifest, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("\n=== reference-capture summary ===")
    print(f"engine: {engine_label}  "
          f"refs seen: {len(refs)}  processed: {len(items)}")
    print(f"ok={counts['ok']}  blocked={counts['blocked']}  dead={counts['dead']}  "
          f"error={counts['error']}  skipped={counts['skipped']}")
    if a.manifest:
        print(f"manifest: {a.manifest}")
    # non-zero exit if anything needs a human (blocked/dead/error).
    needs_human = counts["blocked"] + counts["dead"] + counts["error"]
    return 0 if needs_human == 0 else 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
