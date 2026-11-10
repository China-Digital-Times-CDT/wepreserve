#!/usr/bin/env python3
"""
fetch_extract.py — bot-wall-tolerant HTML fetch + clean full-text extraction.

The local Tier-1 text engine, with the capture technique ported from the
here.news Forensic Center (per the hybrid decision in reports/capture-pipeline.md):

  * curl_cffi with browser-TLS impersonation beats TLS-fingerprint bot-walls
    cheaply — it fetched The Witness and passiontimes.hk (HTTP 200) where plain
    curl, urllib and headless Browsertrix all got 403;
  * trafilatura extracts clean article text + metadata (title/author/date).

Sites behind a real JS challenge (e.g. a Cloudflare interstitial) return a
challenge page via curl_cffi and are classified 'blocked' — those need the
stealth headful-browser fallback (a separate engine), or the Internet Archive.

Scope: public-interest preservation of public, at-risk journalism
(SaveHKOnline). Public pages only; honours the archive's capture policy.

Usage:
    .capture-venv/bin/python scripts/fetch_extract.py <url> [--out DIR] [--name N]
    # also publish the clean capture to the public R2 mirror:
    .capture-venv/bin/python scripts/fetch_extract.py <url> --r2

With --r2, a clean capture's html/txt/json are uploaded to
r2:shko-public/fulltext/<name>/<ts>.* (served at pub-*.r2.dev) via the
pre-configured rclone `r2` remote — only on status 'ok' (a blocked/challenge or
dead page is never stored as the archive), and public pages only.
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

# Public mirror: shko-public is served read-only at this r2.dev host (and,
# eventually, archive.savehkonline.org). Only Tier-1 PUBLIC-page captures land
# here; authenticated/cookie-bearing captures never do (capture policy / #43).
R2_PUBLIC_BUCKET = "shko-public"
R2_PUBLIC_BASE = "https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev"
R2_PREFIX = "fulltext"
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
}

# STRONG markers only appear on an actual interstitial/challenge page — a hit
# means blocked regardless of size.
STRONG_MARKERS = (
    "performing security verification",
    "checking your browser before accessing",
    "just a moment...",
    "attention required! | cloudflare",
    "ddos protection by cloudflare",
    "enable javascript and cookies to continue",
    "verify you are human",
    "verifying you are human",
)
# WEAK markers (Cloudflare's challenge/turnstile script tags) are ALSO present
# in the HTML of legit pages fronted by Cloudflare — e.g. thewitnesshk.com
# serves a real 234 KB homepage that embeds `challenge-platform`. So these only
# indicate a block on a small page or a 4xx/5xx status, never on a large 200.
WEAK_MARKERS = (
    "cf-browser-verification",
    "challenge-platform",
    "__cf_chl",
    "cf_chl_opt",
)
SMALL_PAGE = 15000  # bytes; genuine challenge pages are tiny (~5 KB)


def _iso_now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _sha256(b):
    return hashlib.sha256(b).hexdigest()


def fetch(url, impersonate="chrome", timeout=30):
    """Fetch HTML via curl_cffi's browser impersonation. Returns (html, status)."""
    from curl_cffi import requests as cr  # imported lazily (venv dep)
    r = cr.get(url, impersonate=impersonate, timeout=timeout, allow_redirects=True)
    return r.text, r.status_code


def classify(html, status):
    """(status_label, note): ok | blocked | dead.

    Discriminates a real page that merely embeds Cloudflare's challenge script
    (large 200) from an actual interstitial (small page / 4xx) — see WEAK_MARKERS.
    """
    low = html.lower()
    size = len(html)
    if any(m in low for m in STRONG_MARKERS):
        return "blocked", f"interstitial challenge (HTTP {status}, {size} chars)"
    if status in (401, 403, 429, 503):
        return "blocked", f"HTTP {status}"
    if size < SMALL_PAGE and any(m in low for m in WEAK_MARKERS):
        return "blocked", f"challenge script on small page (HTTP {status}, {size} chars)"
    if status >= 400:
        return "dead", f"HTTP {status}"
    if size < 200:
        return "dead", f"empty/near-empty response ({size} chars)"
    return "ok", f"HTTP {status}"


def extract(html, url):
    """Return (text, metadata-dict) via trafilatura."""
    import trafilatura  # lazy (venv dep)
    text = trafilatura.extract(
        html, url=url, include_comments=False, include_tables=True,
        favor_precision=True) or ""
    md = {}
    try:
        meta = trafilatura.extract_metadata(html)
        if meta:
            md = {"title": meta.title, "author": meta.author,
                  "date": meta.date, "sitename": meta.sitename}
    except Exception:
        pass
    return text, md


def capture_text(url, impersonate="chrome", timeout=30):
    """Fetch + classify + extract. Returns a provenance dict (no disk writes)."""
    rec = {"url": url, "captured_at": _iso_now(), "engine": "cffi"}
    try:
        html, status = fetch(url, impersonate, timeout)
    except Exception as e:
        rec.update(status="error", note=f"{type(e).__name__}: {e}")
        return rec, None
    st, note = classify(html, status)
    rec.update(status=st, note=note, http_status=status,
               html_bytes=len(html.encode("utf-8")),
               html_sha256=_sha256(html.encode("utf-8")))
    if st == "ok":
        text, md = extract(html, url)
        rec.update(text_chars=len(text), title=md.get("title"),
                   author=md.get("author"), date=md.get("date"),
                   sitename=md.get("sitename"))
        return rec, (html, text)
    return rec, (html, None)


def _name_for(url):
    host = re.sub(r"^www\.", "", url.split("//", 1)[-1].split("/", 1)[0].lower())
    tag = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return re.sub(r"[^a-z0-9.-]+", "-", host).strip("-") + "-" + tag


def _rclone():
    return shutil.which("rclone") or os.path.expanduser("~/bin/rclone")


def upload_r2(local_path, key, bucket=R2_PUBLIC_BUCKET, remote="r2"):
    """Upload one file to r2:<bucket>/<key> with the right Content-Type.

    Uses the pre-configured rclone `r2` remote (same creds as r2-sync-wacz.sh;
    no secrets in this script). Returns the public URL on success, else raises.
    """
    rclone = _rclone()
    if not os.path.exists(rclone):
        raise RuntimeError("rclone not found (need ~/bin/rclone or on PATH)")
    ctype = _CONTENT_TYPES.get(os.path.splitext(key)[1], "application/octet-stream")
    cmd = [rclone, "copyto", local_path, f"{remote}:{bucket}/{key}",
           "--header-upload", f"Content-Type: {ctype}", "--s3-no-head"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(f"rclone upload failed ({res.returncode}): "
                           f"{res.stderr.strip() or res.stdout.strip()}")
    return f"{R2_PUBLIC_BASE}/{key}" if bucket == R2_PUBLIC_BUCKET else None


def capture_to_dir(url, out_dir, name, impersonate="chrome", do_r2=False):
    """Capture full text for `url`, write html/txt/json under out_dir, and (on a
    clean capture, if do_r2) upload them to the public mirror. Returns the
    provenance record. Shared by this CLI and capture_refs.py's text engine."""
    os.makedirs(out_dir, exist_ok=True)
    rec, payload = capture_text(url, impersonate)
    html_path = txt_path = None
    if payload:
        html, text = payload
        if html is not None:
            html_path = os.path.join(out_dir, name + ".html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            rec["html"] = name + ".html"
        if text:
            txt_path = os.path.join(out_dir, name + ".txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            rec["text"] = name + ".txt"
            rec["text_sha256"] = _sha256(text.encode("utf-8"))

    # Upload to the public mirror only on a clean capture — never store a
    # blocked/challenge or dead page as the archive (same discipline as the
    # screenshot path). Public pages only; see the module docstring / policy.
    if do_r2 and rec["status"] == "ok":
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base_key = f"{R2_PREFIX}/{name}/{ts}"
        try:
            uploaded = {}
            if html_path:
                uploaded["html_url"] = upload_r2(html_path, base_key + ".html")
            if txt_path:
                uploaded["text_url"] = upload_r2(txt_path, base_key + ".txt")
            rec["r2"] = {"bucket": R2_PUBLIC_BUCKET, "key_prefix": base_key, **uploaded}
        except Exception as e:
            rec["r2_error"] = f"{type(e).__name__}: {e}"

    json_path = os.path.join(out_dir, name + ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    # The provenance record is the index into a capture — upload it last so it
    # carries the html/txt R2 urls it points at.
    if do_r2 and rec["status"] == "ok" and "r2" in rec:
        try:
            rec["r2"]["json_url"] = upload_r2(
                json_path, rec["r2"]["key_prefix"] + ".json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=2)
        except Exception as e:
            rec["r2_error"] = f"{type(e).__name__}: {e}"
    rec["_json_path"] = json_path
    return rec


def main(argv):
    ap = argparse.ArgumentParser(description="Fetch + extract full text (#36, Tier-1).")
    ap.add_argument("url")
    ap.add_argument("--out", default="captures")
    ap.add_argument("--name")
    ap.add_argument("--impersonate", default="chrome")
    ap.add_argument("--r2", action="store_true",
                    help=f"on a clean capture, also upload html/txt/json to "
                         f"r2:{R2_PUBLIC_BUCKET}/{R2_PREFIX}/<name>/<ts>.*")
    a = ap.parse_args(argv)
    name = a.name or _name_for(a.url)

    rec = capture_to_dir(a.url, a.out, name, a.impersonate, do_r2=a.r2)
    json_path = rec.pop("_json_path")

    icon = {"ok": "✓", "blocked": "⛔", "dead": "✗", "error": "⚠"}.get(rec["status"], "?")
    print(f"{icon} {rec['status']:<7} {a.url}")
    print(f"  {rec.get('note','')}")
    if rec.get("title"):
        print(f"  title: {rec['title']}")
    if rec.get("text_chars"):
        print(f"  full text: {rec['text_chars']} chars -> {rec.get('text')}")
    if rec.get("r2"):
        print(f"  r2: {rec['r2'].get('text_url') or rec['r2'].get('html_url')}")
    if rec.get("r2_error"):
        print(f"  r2 upload FAILED: {rec['r2_error']}")
    print(f"  provenance: {json_path}")
    return {"ok": 0, "blocked": 2, "dead": 3, "error": 4}.get(rec["status"], 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
