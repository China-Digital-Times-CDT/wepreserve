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
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys

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


def main(argv):
    ap = argparse.ArgumentParser(description="Fetch + extract full text (#36, Tier-1).")
    ap.add_argument("url")
    ap.add_argument("--out", default="captures")
    ap.add_argument("--name")
    ap.add_argument("--impersonate", default="chrome")
    a = ap.parse_args(argv)
    name = a.name or _name_for(a.url)
    os.makedirs(a.out, exist_ok=True)

    rec, payload = capture_text(a.url, a.impersonate)
    if payload:
        html, text = payload
        if html is not None:
            with open(os.path.join(a.out, name + ".html"), "w", encoding="utf-8") as f:
                f.write(html)
            rec["html"] = name + ".html"
        if text:
            with open(os.path.join(a.out, name + ".txt"), "w", encoding="utf-8") as f:
                f.write(text)
            rec["text"] = name + ".txt"
            rec["text_sha256"] = _sha256(text.encode("utf-8"))
    with open(os.path.join(a.out, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)

    icon = {"ok": "✓", "blocked": "⛔", "dead": "✗", "error": "⚠"}.get(rec["status"], "?")
    print(f"{icon} {rec['status']:<7} {a.url}")
    print(f"  {rec.get('note','')}")
    if rec.get("title"):
        print(f"  title: {rec['title']}")
    if rec.get("text_chars"):
        print(f"  full text: {rec['text_chars']} chars -> {rec.get('text')}")
    print(f"  provenance: {os.path.join(a.out, name + '.json')}")
    return {"ok": 0, "blocked": 2, "dead": 3, "error": 4}.get(rec["status"], 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
