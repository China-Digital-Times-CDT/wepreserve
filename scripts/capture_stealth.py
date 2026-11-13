#!/usr/bin/env python3
"""
capture_stealth.py — Tier-1 fallback for sites behind a real JS challenge.

Some sites (e.g. hkja.org.hk) sit behind a Cloudflare *interstitial* that a
plain headless render and even the curl_cffi text engine can't pass: they serve
a "just a moment…" / "performing security verification" page that only clears
after the browser runs the challenge JavaScript. This engine drives a REAL,
non-headless Chrome (on a virtual X display) with the automation fingerprints
masked, waits for the challenge to clear, then captures the actual page —
yielding BOTH a full-page screenshot AND clean full text.

Technique ported from the here.news Forensic Center archive worker (the hybrid
decision in reports/capture-pipeline.md): Playwright `channel="chrome"` headful
with `--disable-blink-features=AutomationControlled`, a stealth init script,
and desktop headers. This is the heaviest Tier-1 path — use it only for URLs the
lighter engines (`fetch_extract`, the edge worker) return `blocked` on.

Scope: public-interest preservation of PUBLIC, at-risk journalism (SaveHKOnline).
Public pages only. No authenticated/cookie-bearing captures here — those stay on
the dedicated local path and the private `shko` bucket (capture policy / #43).

Requires (installed separately, see reports/capture-pipeline.md):
    * a system Chrome (google-chrome-stable) — used via channel="chrome"
    * Xvfb (virtual display) — run this script under `xvfb-run`
    * the `playwright` python package in .capture-venv

Usage (always under a virtual display):
    xvfb-run -a .capture-venv/bin/python scripts/capture_stealth.py <url> \
        [--out DIR] [--name N] [--r2] [--wait SECONDS]
"""
import argparse
import datetime as _dt
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture_page  # noqa: E402  — reuse the shared ok/blocked/dead classifier
import fetch_extract  # noqa: E402  — reuse extract() + upload_r2() + R2 layout

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Desktop headers a real Chrome sends; a bare automation context omits several
# of these and that absence is itself a bot signal.
DESKTOP_HEADERS = {
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,image/apng,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9,zh-HK;q=0.8",
    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Upgrade-Insecure-Requests": "1",
}

# Mask the headless/automation tells the challenge JS looks for.
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en','zh-HK']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = { runtime: {} };
const _q = window.navigator.permissions && window.navigator.permissions.query;
if (_q) {
  window.navigator.permissions.query = (p) => (
    p && p.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : _q(p)
  );
}
"""

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--window-size=1280,1600",
    "--lang=en-US",
]

# Best-effort cookie/consent dismissal so the screenshot shows the page, not a
# banner. Tried in order; failures are ignored.
CONSENT_SELECTORS = (
    "#onetrust-accept-btn-handler",
    "button[aria-label='Accept']",
    "button:has-text('Accept all')",
    "button:has-text('I agree')",
    "button:has-text('同意')",
    "button:has-text('接受')",
)


def _dismiss_consent(page):
    for sel in CONSENT_SELECTORS:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=1500)
                page.wait_for_timeout(400)
                return sel
        except Exception:
            pass
    return None


def capture(url, out_dir, name, wait_s=12.0, do_r2=False, profile_dir=None):
    """Drive a stealthed real Chrome, wait out a JS challenge, capture the page.

    Returns a provenance dict. Writes <name>.png / .html / .txt / .json under
    out_dir; with do_r2 and a clean capture, uploads them to the public mirror.
    """
    from playwright.sync_api import sync_playwright  # lazy (venv dep)

    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, name + ".png")
    html_path = os.path.join(out_dir, name + ".html")
    txt_path = os.path.join(out_dir, name + ".txt")
    json_path = os.path.join(out_dir, name + ".json")

    rec = {"url": url, "name": name,
           "captured_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
           "engine": "stealth"}
    html = ""
    http_status = None
    consent = None

    tmp_profile = None
    with sync_playwright() as p:
        if profile_dir:
            # Reuse a warmed Chrome profile (one that already solved the
            # Cloudflare challenge in a real session). cf_clearance is bound to
            # the browser's NATIVE User-Agent + IP, so here we must NOT override
            # UA / headers / stealth — Chrome's real identity is what the cookie
            # was issued to; overriding it gets the cookie rejected and the
            # challenge returns. Work on a cache-excluded COPY so the operator's
            # real profile is never locked or mutated. (Quit Chrome first so the
            # cookie DB is flushed.)
            tmp_profile = tempfile.mkdtemp(prefix="stealth-prof-",
                                           dir=os.environ.get("TMPDIR") or None)
            _ignore = shutil.ignore_patterns(
                "Cache", "Code Cache", "GPUCache", "ShaderCache", "GrShaderCache",
                "*Cache*", "Service Worker", "component_crx_cache",
                "extensions_crx_cache", "Crashpad", "*.log")
            shutil.copytree(profile_dir, os.path.join(tmp_profile, "prof"),
                            ignore=_ignore, dirs_exist_ok=True,
                            symlinks=True, ignore_dangling_symlinks=True)
            ctx = p.chromium.launch_persistent_context(
                os.path.join(tmp_profile, "prof"), channel="chrome",
                headless=False, args=LAUNCH_ARGS, locale="en-US",
                viewport={"width": 1280, "height": 1600}, no_viewport=False)
            browser = ctx.browser
            rec["engine"] = "stealth+profile"
        else:
            browser = p.chromium.launch(channel="chrome", headless=False,
                                        args=LAUNCH_ARGS)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 1600},
                user_agent=UA, locale="en-US",
                extra_http_headers=DESKTOP_HEADERS)
            ctx.add_init_script(STEALTH_JS)
        try:
            page = ctx.pages[0] if (profile_dir and ctx.pages) else ctx.new_page()
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                http_status = resp.status if resp else None
            except Exception as e:
                rec.update(status="dead", note=f"navigation failed: "
                           f"{type(e).__name__}: {e}")
                return _finish(rec, json_path)

            # Grabbing content while Cloudflare's challenge is reloading the
            # page races the navigation (Playwright: "page is navigating and
            # changing the content"). Retry through transient navigations
            # instead of letting the whole capture crash.
            def _grab():
                for _ in range(6):
                    try:
                        return page.content()
                    except Exception:
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=4000)
                        except Exception:
                            page.wait_for_timeout(500)
                return ""

            # Poll until the challenge clears (a real browser solves Cloudflare's
            # interstitial in a few seconds) or we exhaust the wait budget.
            deadline = wait_s
            step = 1.5
            waited = 0.0
            while True:
                page.wait_for_timeout(int(step * 1000))
                waited += step
                html = _grab()
                status, note = capture_page.classify(html, None)
                if status != "blocked" or waited >= deadline:
                    break

            # Let the post-challenge page settle before the real capture.
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            consent = _dismiss_consent(page)
            html = _grab()
            try:
                page.screenshot(path=png_path, full_page=True)
            except Exception:
                try:
                    page.screenshot(path=png_path)  # viewport-only fallback
                except Exception:
                    pass
        finally:
            try:
                ctx.close()
            except Exception:
                pass
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
    if tmp_profile:
        shutil.rmtree(tmp_profile, ignore_errors=True)

    status, note = capture_page.classify(html, png_path if os.path.exists(png_path) else None)
    rec.update(status=status, note=note, http_status=http_status,
               challenge_wait_s=wait_s, consent_dismissed=consent)

    # Never keep a challenge/dead screenshot as if it were the archive.
    png_final = None
    if os.path.exists(png_path):
        if status == "ok":
            png_final = png_path
            rec.update(screenshot=name + ".png",
                       screenshot_bytes=os.path.getsize(png_path),
                       screenshot_sha256=fetch_extract._sha256(open(png_path, "rb").read()))
        else:
            os.replace(png_path, png_path + f".{status}")

    if html:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        rec.update(html=name + ".html", html_bytes=len(html.encode("utf-8")),
                   html_sha256=fetch_extract._sha256(html.encode("utf-8")))

    if status == "ok" and html:
        text, md = fetch_extract.extract(html, url)
        if text:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            rec.update(text=name + ".txt", text_chars=len(text),
                       text_sha256=fetch_extract._sha256(text.encode("utf-8")),
                       title=md.get("title"), author=md.get("author"),
                       date=md.get("date"), sitename=md.get("sitename"))

    # Publish to the public mirror only on a clean capture, public pages only.
    if do_r2 and status == "ok":
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base_key = f"screenshots/{name}/{ts}"  # share the edge worker's prefix
        try:
            up = {}
            if png_final:
                up["screenshot_url"] = fetch_extract.upload_r2(png_final, base_key + ".png")
            if rec.get("html"):
                up["html_url"] = fetch_extract.upload_r2(html_path, base_key + ".html")
            if rec.get("text"):
                up["text_url"] = fetch_extract.upload_r2(txt_path, base_key + ".txt")
            rec["r2"] = {"bucket": fetch_extract.R2_PUBLIC_BUCKET,
                         "key_prefix": base_key, **up}
        except Exception as e:
            rec["r2_error"] = f"{type(e).__name__}: {e}"

    return _finish(rec, json_path, upload=do_r2)


def _finish(rec, json_path, upload=False):
    import json
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    if upload and rec.get("status") == "ok" and "r2" in rec:
        try:
            rec["r2"]["json_url"] = fetch_extract.upload_r2(
                json_path, rec["r2"]["key_prefix"] + ".json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=2)
        except Exception as e:
            rec["r2_error"] = f"{type(e).__name__}: {e}"
    rec["_json_path"] = json_path
    return rec


def main(argv):
    ap = argparse.ArgumentParser(
        description="Stealth headful-browser capture for JS-challenge sites (Tier-1).")
    ap.add_argument("url")
    ap.add_argument("--out", default="captures")
    ap.add_argument("--name")
    ap.add_argument("--wait", type=float, default=12.0,
                    help="max seconds to wait for a JS challenge to clear")
    ap.add_argument("--r2", action="store_true",
                    help="on a clean capture, publish png/html/txt/json to "
                         "r2:shko-public/screenshots/<name>/<ts>.* (public pages only)")
    ap.add_argument("--profile", default=None,
                    help="reuse a warmed Chrome profile dir (e.g. "
                         "~/.config/google-chrome) whose cf_clearance already "
                         "cleared the challenge. Uses Chrome's native identity "
                         "on a cache-excluded copy. QUIT Chrome first.")
    a = ap.parse_args(argv)
    name = a.name or fetch_extract._name_for(a.url)
    profile_dir = os.path.expanduser(a.profile) if a.profile else None
    if profile_dir and not os.path.isdir(profile_dir):
        print(f"⚠  --profile dir not found: {profile_dir}", file=sys.stderr)
        return 4

    if not os.environ.get("DISPLAY"):
        print("⚠  no DISPLAY set — run this under `xvfb-run -a` "
              "(headful Chrome needs a virtual display).", file=sys.stderr)

    rec = capture(a.url, a.out, name, wait_s=a.wait, do_r2=a.r2,
                  profile_dir=profile_dir)
    json_path = rec.pop("_json_path")
    icon = {"ok": "✓", "blocked": "⛔", "dead": "✗", "error": "⚠"}.get(rec["status"], "?")
    print(f"{icon} {rec['status']:<7} {a.url}")
    print(f"  {rec.get('note','')}")
    if rec.get("title"):
        print(f"  title: {rec['title']}")
    if rec.get("text_chars"):
        print(f"  full text: {rec['text_chars']} chars -> {rec.get('text')}")
    if rec.get("screenshot"):
        print(f"  screenshot: {rec['screenshot']} ({rec['screenshot_bytes']} bytes)")
    if rec.get("r2"):
        print(f"  r2: {rec['r2'].get('screenshot_url') or rec['r2'].get('html_url')}")
    if rec.get("r2_error"):
        print(f"  r2 upload FAILED: {rec['r2_error']}")
    print(f"  provenance: {json_path}")
    return {"ok": 0, "blocked": 2, "dead": 3, "error": 4}.get(rec["status"], 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
