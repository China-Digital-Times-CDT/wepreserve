# Weekly archive health check

Automated weekly review of the SHKO archive. A cloud routine runs every
**Monday 08:00 Hong Kong time** and delivers a dated digest to a **living
Claude Doc** titled **"SHKO Weekly Health Check"** (a new dated section is
prepended each week).

**Delivery note.** The cloud routine has **read-only** access to this repo —
it can clone and read, but it **cannot push** (the Claude GitHub App is not
granted write access). So it does **not** commit anything: the report goes to
the Claude Doc, and any mechanical fixes it finds are written as a checklist
for a maintainer to apply locally from a normal `git` checkout. (This
directory is kept for the recipe and for manually-saved reports.)

## What the weekly check does (v1)

1. **Read latest `main`** (read-only; never push).
2. **Deterministic checks** — run `python3 scripts/check_archive.py`:
   broken wikilinks (incl. reversed `[[Alias|target]]` order and case
   mismatches), missing frontmatter, stale "due/expected <Month YYYY>" lines
   whose date has passed, hub pages missing a Sources/香港中文報道 block,
   and orphan pages.
3. **Coherence & readability** — read the core hubs and key subpages; flag
   cross-page contradictions (a date, death toll, or sentence length that
   disagrees between two pages), placeholder/TODO leftovers, and awkward or
   overlong sections.
4. **News & updates sweep** — for each core topic, search roughly the last
   7–10 days for developments (rulings, sentencings, arrests, closures, new
   films/reports/collections). **Before flagging an item as missing, grep the
   vault to confirm it isn't already covered.** List candidates **with
   sources**, following the archive's sourcing rules: a range of real
   international journalism plus Traditional-Chinese HK outlets (The Witness,
   InMedia, 端傳媒, zh.wikipedia); never state/establishment media.
5. **Deliver to the Claude Doc** — maintain one living doc titled
   "SHKO Weekly Health Check"; prepend a new `## YYYY-MM-DD` section holding
   the digest, ranked 🔴 must-fix / 🟡 should-update / 🟢 nice-to-have, plus a
   Watchlist-status line. Mechanical fixes are a checklist for a maintainer.
6. **Notify** — send a push notification with the doc link and severity counts.

## Core topics

background · book-censorship · faces-of-the-crackdown (+ person pages) ·
films · glory-to-hong-kong · hong-kong-47 · hong-kong-fire-2025 (+ subpages)
· press-freedom · statues · tiananmen-vigil · the Alliance / 8964 · the
preserved-sites index.

## Known pending events to watch

Keep these from going stale — update the relevant page when they land:

- **Pillar of Shame** confiscation ruling (separate routine already watches `statues.md`).
- **Wang Fuk Court fire** independent committee final report — due ~late Oct 2026.
- **Jason Kong** (fire petition organiser) fraud trial.
- **Ronson Chan** — Court of Final Appeal leave application on his obstruction conviction.
- **Jimmy Lai** — NSL trial verdict / sentencing.
- **Joshua Wong** — sentencing on the second (foreign-collusion) charge.
- **EU** — whether the Council acts on the Parliament's sanctions call (the Parliament's resolution is already recorded on `sites.hka`).

## Improving it over time

This is v1, deliberately simple. Candidate upgrades: a persistent watchlist
so the news sweep only surfaces genuinely new items; per-topic parallel
review agents; external-link and image liveness checks; and — if the GitHub
App is ever granted write — switching delivery back to committed reports +
auto-PRs for the mechanical fixes.
