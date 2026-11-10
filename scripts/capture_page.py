#!/usr/bin/env python3
"""
capture_page.py — on-demand single-page capture with block/challenge detection.

The local/residential backbone of the capture pipeline (issues #40/#41/#36).
Renders a URL in a REAL headless Chrome (not an HTTP fetch, so it gets through
bot-walls that 403 curl), writes a full-page screenshot + the rendered DOM, and
— crucially — classifies the result so we NEVER store a bot-challenge page as if
it were the archive:

    ok      the real page rendered         -> artifacts written, exit 0
    blocked a challenge / verification wall -> flagged, exit 2
    dead    nothing rendered (DNS/conn)     -> flagged, exit 3

Every capture also writes a provenance JSON (url, UTC time, sha256s, sizes,
status) so each stored copy is traceable. This is the detect-and-classify
requirement hard-won on the 2026-11-10 test, where hkja.org.hk returned a
Cloudflare "Performing security verification" page even via a real browser.

Usage:
    python3 scripts/capture_page.py <url> [--out DIR] [--name NAME]
    python3 scripts/capture_page.py https://hongkongfp.com/ --name hkfp

Tier-0 cooperative sites and the heavy WACZ path have their own tools
(Cloudflare Browser Run for #41, Browsertrix for #42); this is the Tier-1
fallback + the reference-URL cold-copy engine for #36.
"""
import argparse
import datetime as _dt
import hashlib
import os
import re
import shutil
import subprocess
import sys
import json

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Substrings (lower-cased) that mark an interstitial bot-wall / challenge rather
# than the site itself. If any appears in the rendered DOM, the capture is a
# block, not the archive.
# STRONG markers only appear on an actual interstitial — a hit means blocked.
STRONG_MARKERS = (
    "performing security verification",
    "checking your browser before accessing",
    "just a moment...",
    "attention required! | cloudflare",
    "ddos protection by cloudflare",
    "enable javascript and cookies to continue",
    "verify you are human",
    "verifying you are human",
    "please turn javascript on and reload the page",
)
# WEAK markers (Cloudflare challenge/turnstile script tags) are ALSO present in
# legit Cloudflare-fronted pages (e.g. thewitnesshk.com's real 234 KB homepage
# embeds `challenge-platform`), so they only indicate a block on a small DOM.
WEAK_MARKERS = (
    "cf-browser-verification",
    "challenge-platform",
    "__cf_chl",
    "cf_chl_opt",
)
SMALL_PAGE = 15000  # chars; genuine challenge DOMs are tiny

# Markers that mean the browser could not reach a live site at all.
DEAD_MARKERS = (
    "this site can&#39;t be reached",
    "this site can’t be reached",
    "err_name_not_resolved",
    "err_connection_refused",
    "err_connection_timed_out",
    "dns_probe_finished_nxdomain",
)


def _chrome():
    for exe in ("google-chrome-stable", "google-chrome", "chromium",
                "chromium-browser"):
        p = shutil.which(exe)
        if p:
            return p
    sys.exit("capture_page: no Chrome/Chromium on PATH")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _render_dom(chrome, url, budget_ms=18000):
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--disable-dev-shm-usage", f"--user-agent={UA}",
           f"--virtual-time-budget={budget_ms}", "--dump-dom", url]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=90)
        return out.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return ""


def _screenshot(chrome, url, path, budget_ms=18000, size="1280,1600"):
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--disable-dev-shm-usage", f"--user-agent={UA}",
           f"--window-size={size}", f"--virtual-time-budget={budget_ms}",
           f"--screenshot={path}", url]
    try:
        subprocess.run(cmd, capture_output=True, timeout=90)
    except subprocess.TimeoutExpired:
        pass
    return os.path.exists(path) and os.path.getsize(path) > 0


def classify(dom, png_path):
    """Return (status, note). status in {ok, blocked, dead}."""
    low = dom.lower()
    for m in STRONG_MARKERS:
        if m in low:
            return "blocked", f"interstitial challenge: {m!r}"
    for m in DEAD_MARKERS:
        if m in low:
            return "dead", f"unreachable marker: {m!r}"
    # No DOM at all -> the render failed (timeout / crash / dead host).
    text = re.sub(r"<[^>]+>", " ", dom)
    if len(text.strip()) < 200:
        return "dead", "empty/near-empty DOM (no render)"
    # Weak Cloudflare-script markers only mean a block on a small DOM — a large
    # rendered page that merely embeds the challenge script is the real page.
    if len(dom) < SMALL_PAGE and any(m in low for m in WEAK_MARKERS):
        return "blocked", "challenge script on a small page"
    # Secondary heuristic: a real homepage screenshot is rarely tiny. A <~55 KB
    # PNG with otherwise-plausible DOM is suspicious enough to flag for review.
    if png_path and os.path.exists(png_path) and os.path.getsize(png_path) < 55000:
        return "blocked", (f"screenshot only {os.path.getsize(png_path)} bytes "
                           "— likely an interstitial; review before storing")
    return "ok", "rendered page content present"


def capture(url, out_dir, name):
    os.makedirs(out_dir, exist_ok=True)
    chrome = _chrome()
    png = os.path.join(out_dir, f"{name}.png")
    html = os.path.join(out_dir, f"{name}.html")
    meta = os.path.join(out_dir, f"{name}.json")

    dom = _render_dom(chrome, url)
    _screenshot(chrome, url, png)
    status, note = classify(dom, png)

    # On a non-ok capture, do NOT leave a misleading screenshot lying around as
    # if it were the archive — rename it aside for inspection.
    if status != "ok" and os.path.exists(png):
        os.replace(png, png + f".{status}")
        png_final = png + f".{status}"
    else:
        png_final = png if os.path.exists(png) else None

    if dom:
        with open(html, "w", encoding="utf-8") as f:
            f.write(dom)

    record = {
        "url": url,
        "name": name,
        "captured_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "status": status,
        "note": note,
        "screenshot": os.path.basename(png_final) if png_final else None,
        "screenshot_bytes": os.path.getsize(png_final) if png_final else 0,
        "screenshot_sha256": _sha256(png_final) if png_final else None,
        "html": os.path.basename(html) if dom else None,
        "html_bytes": len(dom.encode("utf-8")) if dom else 0,
        "html_sha256": _sha256(html) if dom else None,
    }
    with open(meta, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


def main(argv):
    ap = argparse.ArgumentParser(description="Capture one page with block detection.")
    ap.add_argument("url")
    ap.add_argument("--out", default="captures", help="output directory")
    ap.add_argument("--name", help="basename for artifacts (default: from host)")
    a = ap.parse_args(argv)
    name = a.name or re.sub(r"[^a-z0-9.-]+", "-",
                            re.sub(r"^www\.", "", a.url.split("//", 1)[-1].split("/", 1)[0]).lower())
    rec = capture(a.url, a.out, name)
    icon = {"ok": "✓", "blocked": "⛔", "dead": "✗"}[rec["status"]]
    print(f"{icon} {rec['status']:<7} {a.url}")
    print(f"  {rec['note']}")
    if rec["screenshot"]:
        print(f"  screenshot: {rec['screenshot']} ({rec['screenshot_bytes']} bytes)")
    print(f"  provenance: {os.path.join(a.out, name + '.json')}")
    return {"ok": 0, "blocked": 2, "dead": 3}[rec["status"]]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
