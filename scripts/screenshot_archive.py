#!/usr/bin/env python3
"""
screenshot_archive.py — a monthly, time-series screenshot archive of a curated
set of at-risk sites. History is KEPT, never replaced: every run adds a new
dated capture under r2:shko-public/screenshots/<name>/<ts>.* so a collection
accrues a visual record over time (feeds the thumbnail gallery + a tracking
issue; see reports/capture-pipeline.md).

Targets live in scripts/screenshot_targets.json (curated priority set). For each
capture we store, alongside the full-res PNG the capture engines already write,
a small JPEG thumbnail (<ts>.thumb.jpg) and refresh a public manifest
(screenshots/index.json) the gallery and the monthly routine read.

Modes (combine freely; a plain monthly run is `--capture --manifest`):
    --capture     capture each due target (via the stealth real-browser engine),
                  publish to R2, and make+upload a thumbnail. Needs a display —
                  run under `xvfb-run -a` and the capture venv's python.
    --thumbs      (re)generate thumbnails for R2 captures that lack one.
    --manifest    rebuild screenshots/index.json from what's in R2 (no capture).
    --report      print a freshness table (last capture + age per target).

    --only NAME   restrict to one target (repeatable)
    --include-residential   also attempt residential-only targets (e.g. hkja)
                  from this host — they will usually come back `blocked` off a
                  datacenter IP; default skips them with a note.
    --wait N      per-capture challenge-wait seconds (default 15)

Example (monthly, under the virtual display):
    xvfb-run -a .capture-venv/bin/python scripts/screenshot_archive.py \
        --capture --manifest --report
"""
import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_extract  # noqa: E402  — R2_PUBLIC_BASE, upload_r2, _rclone
import capture_stealth  # noqa: E402  — the real-browser capture engine

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS_FILE = os.path.join(HERE, "screenshot_targets.json")
# A committed copy of the manifest, so the monthly cloud audit routine can read
# freshness from its git checkout — the cloud sandbox's egress proxy blocks the
# public R2 host, and this also versions the archive's growth over time.
REPO_MANIFEST = os.path.normpath(os.path.join(HERE, "..", "reports", "screenshot-index.json"))
PREFIX = "screenshots"
BUCKET = fetch_extract.R2_PUBLIC_BASE  # public URL base
REMOTE_BUCKET = "shko-public"
TS_RE = re.compile(r"^(\d{8}T\d{6}Z)$")  # capture_stealth's UTC compact stamp


def load_targets(path=TARGETS_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["targets"]


def _rclone():
    return shutil.which("rclone") or os.path.expanduser("~/bin/rclone")


def _rclone_lsjson(prefix):
    """List one R2 prefix. Returns a list of {Name, Size} dicts (files only)."""
    out = subprocess.run(
        [_rclone(), "lsjson", f"r2:{REMOTE_BUCKET}/{prefix}", "--files-only"],
        capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        return []
    try:
        return json.loads(out.stdout or "[]")
    except ValueError:
        return []


def _make_thumb(png_path, thumb_path, width=480, crop_h=360):
    """Top-slice JPEG thumbnail via ImageMagick (uniform gallery cards)."""
    convert = shutil.which("convert") or shutil.which("magick")
    if not convert:
        raise RuntimeError("ImageMagick `convert` not found")
    cmd = [convert, png_path, "-resize", f"{width}x",
           "-background", "white", "-flatten",
           "-crop", f"{width}x{crop_h}+0+0", "+repage",
           "-strip", "-quality", "82", thumb_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or not os.path.exists(thumb_path):
        raise RuntimeError(f"convert failed: {r.stderr.strip()}")


def capture_one(t, out_dir, wait, include_residential):
    """Capture one target, publish PNG+thumbnail to its dated R2 prefix.
    Returns (status, note, r2_prefix|None)."""
    name = t["name"]
    if t.get("residential_only") and not include_residential:
        return "skipped", "residential-only (needs a non-datacenter IP)", None

    rec = capture_stealth.capture(t["url"], out_dir, name, wait_s=wait, do_r2=True)
    status = rec.get("status")
    if status != "ok" or "r2" not in rec:
        return status, rec.get("note") or rec.get("r2_error") or "", None

    # Thumbnail from the local full-res PNG → upload beside the capture.
    key_prefix = rec["r2"]["key_prefix"]  # screenshots/<name>/<ts>
    png_local = os.path.join(out_dir, name + ".png")
    thumb_local = os.path.join(out_dir, name + ".thumb.jpg")
    try:
        _make_thumb(png_local, thumb_local)
        fetch_extract.upload_r2(thumb_local, key_prefix + ".thumb.jpg")
    except Exception as e:
        return status, f"captured ok but thumbnail failed: {e}", key_prefix
    return status, rec.get("note", ""), key_prefix


def iter_captures(name):
    """Yield {ts, iso, png_url, thumb_url, bytes} for a target, newest last."""
    rows = _rclone_lsjson(f"{PREFIX}/{name}")
    by_ts = {}
    for r in rows:
        fn = r.get("Name", "")
        if fn.endswith(".thumb.jpg"):
            ts = fn[:-len(".thumb.jpg")]
            kind, key = "thumb", ts
        elif fn.endswith(".png"):
            ts = fn[:-len(".png")]
            kind, key = "png", ts
        else:
            continue
        if not TS_RE.match(key):
            continue
        e = by_ts.setdefault(key, {})
        if kind == "png":
            e["bytes"] = r.get("Size")
        e[kind] = True
    caps = []
    for ts, e in by_ts.items():
        if "png" not in e:
            continue  # a thumb with no master is not a capture
        base = f"{BUCKET}/{PREFIX}/{name}/{ts}"
        iso = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}T{ts[9:11]}:{ts[11:13]}:{ts[13:15]}Z"
        caps.append({"ts": ts, "iso": iso, "png_url": base + ".png",
                     "thumb_url": base + ".thumb.jpg" if "thumb" in e else None,
                     "bytes": e.get("bytes")})
    caps.sort(key=lambda c: c["ts"])
    return caps


def build_manifest(targets):
    out = {"generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
           "base": BUCKET, "targets": []}
    for t in targets:
        caps = iter_captures(t["name"])
        out["targets"].append({
            "name": t["name"], "title": t.get("title", t["name"]),
            "url": t["url"], "collection": t.get("collection", ""),
            "tier": t.get("tier", 0),
            "residential_only": bool(t.get("residential_only")),
            "count": len(caps), "captures": caps,
            "latest": caps[-1] if caps else None})
    return out


def publish_manifest(manifest, out_dir):
    local = os.path.join(out_dir, "index.json")
    os.makedirs(out_dir, exist_ok=True)
    blob = json.dumps(manifest, ensure_ascii=False, indent=2)
    with open(local, "w", encoding="utf-8") as f:
        f.write(blob)
    # 1) public copy in R2 (the browser gallery fetches this cross-origin)
    fetch_extract.upload_r2(local, f"{PREFIX}/index.json")
    # 2) committed copy in the repo (the cloud audit routine reads this; the
    #    sandbox can't reach R2). Only written when the reports/ dir exists.
    if os.path.isdir(os.path.dirname(REPO_MANIFEST)):
        with open(REPO_MANIFEST, "w", encoding="utf-8") as f:
            f.write(blob)
    return local, f"{BUCKET}/{PREFIX}/index.json"


def _age_days(iso):
    try:
        t = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (_dt.datetime.now(_dt.timezone.utc) - t).days
    except Exception:
        return None


def report(manifest, overdue_days=35):
    print("\n=== screenshot-archive freshness ===")
    print(f"{'target':<14}{'tier':<6}{'count':<7}{'last capture':<22}{'age':<8}flag")
    for t in manifest["targets"]:
        latest = t["latest"]
        last = latest["iso"] if latest else "—"
        age = _age_days(latest["iso"]) if latest else None
        flag = ""
        if t["residential_only"] and not latest:
            flag = "residential-run pending"
        elif age is None and not latest:
            flag = "NEVER captured"
        elif age is not None and age > overdue_days:
            flag = f"OVERDUE (>{overdue_days}d)"
        age_s = f"{age}d" if age is not None else "—"
        print(f"{t['name']:<14}{('T'+str(t['tier'])):<6}{t['count']:<7}"
              f"{last:<22}{age_s:<8}{flag}")


def main(argv):
    ap = argparse.ArgumentParser(description="Monthly time-series screenshot archive.")
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--thumbs", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--only", action="append", default=[], metavar="NAME")
    ap.add_argument("--include-residential", action="store_true")
    ap.add_argument("--wait", type=float, default=15.0)
    ap.add_argument("--out", default=os.path.join(os.getcwd(), "captures", "shots"))
    a = ap.parse_args(argv)
    if not any([a.capture, a.thumbs, a.manifest, a.report]):
        ap.error("pick at least one of --capture/--thumbs/--manifest/--report")

    targets = load_targets()
    if a.only:
        targets = [t for t in targets if t["name"] in a.only]
        if not targets:
            sys.exit(f"no target matches --only {a.only}")

    if a.capture:
        if not os.environ.get("DISPLAY"):
            print("⚠  no DISPLAY — run under `xvfb-run -a` (headful Chrome).",
                  file=sys.stderr)
        os.makedirs(a.out, exist_ok=True)
        for t in targets:
            st, note, prefix = capture_one(t, a.out, a.wait, a.include_residential)
            icon = {"ok": "✓", "blocked": "⛔", "dead": "✗",
                    "skipped": "·", "error": "⚠"}.get(st, "?")
            print(f"{icon} {st:<8} {t['name']:<12} {note}")
            if prefix:
                print(f"    -> r2:{REMOTE_BUCKET}/{prefix}.{{png,thumb.jpg}}")

    if a.thumbs:
        for t in targets:
            for cap in iter_captures(t["name"]):
                if cap["thumb_url"]:
                    continue
                # Fetch the PNG, thumb it, upload. (Rare backfill path.)
                import urllib.request
                tmp_png = os.path.join(a.out, t["name"] + "-bf.png")
                tmp_thumb = os.path.join(a.out, t["name"] + "-bf.thumb.jpg")
                os.makedirs(a.out, exist_ok=True)
                try:
                    urllib.request.urlretrieve(cap["png_url"], tmp_png)
                    _make_thumb(tmp_png, tmp_thumb)
                    fetch_extract.upload_r2(
                        tmp_thumb, f"{PREFIX}/{t['name']}/{cap['ts']}.thumb.jpg")
                    print(f"✓ thumb backfilled {t['name']}/{cap['ts']}")
                except Exception as e:
                    print(f"⚠ thumb backfill failed {t['name']}/{cap['ts']}: {e}")

    if a.manifest or a.report:
        manifest = build_manifest(targets)
        if a.manifest:
            local, url = publish_manifest(manifest, a.out)
            print(f"manifest -> {url}  (local: {local})")
        if a.report:
            report(manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
