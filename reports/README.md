# Weekly archive health check

Automated weekly review of the SHKO archive. A cloud routine runs every
**Monday 08:00 Hong Kong time** and writes a dated digest here
(`reports/weekly-YYYY-MM-DD.md`). Files in `reports/` live **outside
`vault/`**, so the publish pipeline never serves them — this is an internal
log, not a published page.

## What the weekly check does (v1)

1. **Pull latest `main`.**
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
   films/reports/collections). List candidates **with sources**, following
   the archive's sourcing rules: a range of real international journalism
   plus Traditional-Chinese HK outlets (The Witness, InMedia, 端傳媒,
   zh.wikipedia); never state/establishment media.
5. **Mechanical fixes → PR.** Unambiguous link/alias/frontmatter fixes go on
   a branch as a pull request for review. News and prose changes are
   **proposed in the digest only**, never auto-applied.
6. **Write & commit the digest**, ranked 🔴 must-fix / 🟡 should-update /
   🟢 nice-to-have, then notify.

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
- **EU** — whether the Council acts on the Parliament's sanctions call.

## Improving it over time

This is v1, deliberately simple. Candidate upgrades: a persistent watchlist
so the news sweep only surfaces genuinely new items; per-topic parallel
review agents; external-link and image liveness checks; richer coherence
cross-checks against a facts ledger.
