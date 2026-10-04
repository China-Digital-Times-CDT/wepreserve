#!/usr/bin/env python3
"""
Deterministic health checks for the SHKO Dendron vault.

Part of the weekly archive health check (see reports/README.md). Prints a
Markdown report fragment to stdout and exits non-zero if any 🔴 must-fix
issues are found. Safe to run anytime: it only reads vault/*.md.

Checks:
  1. Broken wikilink targets — [[Alias|target]] / [[target]] where target
     has no matching vault/<target>.md. (This also catches reversed aliases,
     since a reversed [[target|Alias]] puts a non-fname after the pipe.)
  2. Frontmatter hygiene — every page has id, title, updated.
  3. Stale "pending" lines — a page says something is due/expected by a date
     that has already passed (heuristic, for human review).
  4. Convention gaps (informational) — hub/site pages with no "Sources" and
     no "香港中文報道" block.
  5. Orphan pages (informational) — no inbound wikilinks from any other page.
"""
import re
import sys
import glob
import os
import datetime

VAULT = os.path.join(os.path.dirname(__file__), "..", "vault")
VAULT = os.path.normpath(VAULT)
TODAY = datetime.date.today()

MONTHS = ("January|February|March|April|May|June|July|August|September|"
          "October|November|December")

files = sorted(glob.glob(os.path.join(VAULT, "*.md")))
fnames = {os.path.basename(f)[:-3] for f in files}

broken = []          # (file, raw-wikilink, target)
fm_issues = []       # (file, missing-field)
stale = []           # (file, line-excerpt, date)
convention = []      # (file,)
inbound = {fn: 0 for fn in fnames}

WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")

def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm

for f in files:
    fn = os.path.basename(f)[:-3]
    text = open(f, encoding="utf-8").read()
    fm = parse_frontmatter(text)

    for field in ("id", "title", "updated"):
        if not fm.get(field):
            fm_issues.append((fn, field))

    for m in WIKILINK.finditer(text):
        inner = m.group(1)
        target = inner.split("|")[-1].strip() if "|" in inner else inner.strip()
        # strip anchors/headers like target#heading
        target = target.split("#")[0].strip()
        if not target:
            continue
        if target != fn:
            inbound[target] = inbound.get(target, 0) + 1
        if target not in fnames:
            broken.append((fn, f"[[{inner}]]", target))

    # stale pending dates (heuristic): a forward-looking phrase whose date has
    # now passed. Require the date to sit close after a "due/expected/..." cue,
    # and skip clearly historical sentences.
    FWD = ("due", "expected", "pending", "deadline", "next mention",
           "decide by", "report due", "ruling", "verdict", "later this",
           "by the end of")
    HIST = ("formed", "founded", "established", "was born", "born on", "set up in")
    for line in text.splitlines():
        low = line.lower()
        if any(h in low for h in HIST):
            continue
        for dm in re.finditer(rf"({MONTHS})\s+(\d{{4}})", line):
            try:
                d = datetime.datetime.strptime(dm.group(0), "%B %Y").date()
            except ValueError:
                continue
            if (d.year, d.month) >= (TODAY.year, TODAY.month):
                continue  # not in the past
            # is a forward-looking cue within ~35 chars before the date?
            window = low[max(0, dm.start() - 35):dm.start()]
            if any(c in window for c in FWD):
                stale.append((fn, line.strip()[:160], dm.group(0)))
                break

    # convention gaps — only for the top-level thematic hubs (not old site stubs)
    HUBS = ("press-freedom", "films", "statues", "tiananmen-vigil",
            "faces-of-the-crackdown", "hong-kong-47", "book-censorship",
            "glory-to-hong-kong", "hong-kong-fire-2025")
    if fn in HUBS and "Sources" not in text and "香港中文報道" not in text:
        convention.append((fn,))

orphans = sorted(fn for fn, n in inbound.items()
                 if n == 0 and fn not in ("root",) and not fn.endswith(".md"))

# ---- emit markdown fragment ----
out = []
out.append(f"### Deterministic checks (run {TODAY.isoformat()})\n")

out.append(f"- Pages scanned: **{len(files)}**")
out.append(f"- Broken wikilinks: **{len(broken)}**")
out.append(f"- Frontmatter issues: **{len(fm_issues)}**")
out.append(f"- Stale pending-date lines: **{len(stale)}**")
out.append(f"- Orphan pages: **{len(orphans)}**")
out.append(f"- Convention gaps: **{len(convention)}**\n")

if broken:
    out.append("#### 🔴 Broken wikilinks (must fix)")
    for fn, raw, tgt in broken:
        out.append(f"- `{fn}.md`: {raw} → no `{tgt}.md`")
    out.append("")

if fm_issues:
    out.append("#### 🔴 Frontmatter missing fields")
    for fn, field in fm_issues:
        out.append(f"- `{fn}.md`: missing `{field}`")
    out.append("")

if stale:
    out.append("#### 🟡 Stale 'pending' lines (a date has passed — verify/update)")
    for fn, line, d in stale:
        out.append(f"- `{fn}.md` ({d}): {line}")
    out.append("")

if convention:
    out.append("#### 🟢 Pages with no Sources / 香港中文報道 block")
    for (fn,) in convention:
        out.append(f"- `{fn}.md`")
    out.append("")

if orphans:
    out.append("#### 🟢 Orphan pages (no inbound wikilinks)")
    for fn in orphans:
        out.append(f"- `{fn}.md`")
    out.append("")

print("\n".join(out))

# exit non-zero only on 🔴 issues
sys.exit(1 if (broken or fm_issues) else 0)
