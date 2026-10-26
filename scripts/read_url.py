#!/usr/bin/env python3
"""
read_url.py — a small LOCAL page-reading harness for the SHKO archive.

Why this exists: many Hong Kong outlets (The Witness, and sites behind
Cloudflare) return 403/429 to plain HTTP clients and to Claude Code's
WebFetch, so their articles cannot be read for sourcing. This reuses the
approach proven in the here.news reader (`here.newsv1/webapp`): try a plain
request first, then fall back to a real headless Chrome render — which gets
past user-agent / basic bot blocks — and extract clean article text.

LOCAL ONLY: needs google-chrome installed; not for the read-only cloud
routine (that keeps using WebFetch/WebSearch).

Usage:
    python3 scripts/read_url.py <url>              # print title + text
    python3 scripts/read_url.py <url> --json       # JSON {url,title,text,via}
    python3 scripts/read_url.py <url> --render      # force the Chrome path
    python3 scripts/read_url.py <url> --html        # print raw rendered HTML
    python3 scripts/read_url.py <url> --max 12000   # cap text chars (0 = all)

Exit codes: 0 ok, 2 fetch failed, 3 bad usage.
"""
import sys
import json
import shutil
import subprocess

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
# Markers that mean "a plain request got a block page, not the article".
BLOCK_MARKERS = ("just a moment", "cloudflare", "security service",
                 "attention required", "enable javascript and cookies",
                 "access denied", "403 forbidden", "verify you are human")


def _chrome():
    for exe in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        p = shutil.which(exe)
        if p:
            return p
    return None


def fetch_plain(url, timeout=20):
    """Fast path: a normal HTTP GET with a browser UA. Returns html or None."""
    import requests
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "*/*",
                                       "Accept-Language": "en,zh-TW,zh"},
                         timeout=timeout)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    html = r.content.decode(r.encoding or "utf-8", "ignore")
    if any(m in html[:4000].lower() for m in BLOCK_MARKERS):
        return None  # looks like a challenge/block page
    return html


def fetch_render(url, budget_ms=20000):
    """Fallback: render in headless Chrome and dump the DOM. Returns html or None."""
    chrome = _chrome()
    if not chrome:
        return None
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--disable-dev-shm-usage",
           f"--user-agent={UA}", f"--virtual-time-budget={budget_ms}",
           "--dump-dom", url]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=budget_ms/1000 + 25)
    except Exception:
        return None
    html = out.stdout.decode("utf-8", "ignore")
    return html if len(html) > 500 else None


def extract(html):
    """Return (title, text) of the main readable content."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "") or ""
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer",
                     "aside", "form", "svg", "button"]):
        tag.decompose()
    # Pick the densest content container, not merely the first <article>
    # (sidebars/related-post cards are often <article> too).
    candidates = soup.find_all(["article", "main"])
    candidates += soup.find_all(attrs={"class": lambda c: c and any(
        k in " ".join(c).lower() for k in ("article-content", "entry-content",
        "post-content", "article-body", "story", "content"))})
    if soup.body:
        candidates.append(soup.body)
    root = max(candidates, key=lambda el: len(el.get_text(" ", strip=True)),
               default=soup)
    lines = []
    for p in root.get_text("\n").splitlines():
        p = p.strip()
        if p:
            lines.append(p)
    # collapse runs of identical short nav-ish lines, keep order
    text = "\n".join(lines)
    return title, text


def read(url, force_render=False):
    html, via = None, None
    if not force_render:
        html = fetch_plain(url)
        via = "plain" if html else None
    if html is None:
        html = fetch_render(url)
        via = "chrome" if html else None
    return html, via


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 3
    url = args[0]
    maxchars = 16000
    for a in argv:
        if a.startswith("--max"):
            try:
                maxchars = int(a.split("=", 1)[1]) if "=" in a else int(argv[argv.index(a) + 1])
            except Exception:
                pass
    html, via = read(url, force_render="--render" in flags)
    if html is None:
        print(f"FAILED to fetch {url} (both plain and headless-Chrome paths)", file=sys.stderr)
        return 2
    if "--html" in flags:
        sys.stdout.write(html)
        return 0
    title, text = extract(html)
    if maxchars and len(text) > maxchars:
        text = text[:maxchars] + f"\n\n[... truncated at {maxchars} chars ...]"
    if "--json" in flags:
        print(json.dumps({"url": url, "title": title, "text": text, "via": via},
                         ensure_ascii=False, indent=2))
    else:
        print(f"# {title}\n(via {via}: {url})\n")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
