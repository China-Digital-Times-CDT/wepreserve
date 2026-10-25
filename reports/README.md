# Weekly archive health check

Automated weekly review of the SHKO archive. A cloud routine runs every
**Monday 08:00 Hong Kong time** and delivers a dated digest to a **living
Claude Doc** titled **"SHKO Weekly Health Check"** (a new dated section is
prepended each week).

**Delivery note.** This is a **read-only reviewer by design**. The cloud
routine clones and reads `main` but never writes to the repo — it does
**not** commit, push, or open PRs, and it must not try. Edits to the archive
are made **here**, in a normal local checkout, and pushed to `main`
directly (CI rebuilds the live site); the Claude GitHub App is not part of
that path. The routine's only job is to **report**: its digest and a
maintainer fix-checklist go to the living Claude Doc, and a human applies the
fixes locally. (This directory keeps the recipe and manually-saved reports.)

## What the weekly check does (v2)

The check has two halves: an **audit** of the archive as it stands (steps
2–4) and a **scout** for content worth editing in (step 5).

1. **Read latest `main`** (read-only; never push).
2. **Deterministic checks** — run `python3 scripts/check_archive.py`:
   broken wikilinks (incl. reversed `[[Alias|target]]` order and case
   mismatches), missing frontmatter, stale "due/expected <Month YYYY>" lines
   whose date has passed, hub pages missing a Sources/香港中文報道 block,
   and orphan pages.
3. **Structure** — is the archive's shape intact? Hubs should lead to their
   subpages and subpages back to a hub (the *monumental-hub-over-person-pages*
   discipline — comprehensive theme/event hub first, persons branching
   beneath). Flag: orphan or dead-end pages (no inbound/outbound links),
   `#jump-to` / table-of-contents anchors that no longer resolve, subpages
   that have outgrown their hub's summary, and any hub whose "Quick links" no
   longer match its real children.
4. **Coherence, quality & references** — read the core hubs and key subpages
   and judge them as writing *and* as a record:
   - **Coherence** — cross-page contradictions (a date, death toll, name
     romanisation, or count that disagrees between two pages); placeholder /
     TODO leftovers; broken markdown; awkward, overlong, or now-stale
     sections.
   - **References** — does every substantive claim carry a source? Do the
     links still resolve (dead/404, moved)? Do sources follow house rules —
     a *range* of real international journalism (HKFP, SCMP, AP, Reuters, CNN,
     Al Jazeera, Guardian, BBC, RFA) plus Traditional-Chinese HK outlets (The
     Witness/法庭線, InMedia/獨立媒體, 端傳媒, zh.wikipedia)? Two tiers to keep
     separate: **never** cite PRC/HK *state or Party* media (大公報, 文匯報,
     China Daily, Global Times, Xinhua, TVB, guancha) — not as a source for
     anything. **Use sparingly** the big commercial HK outlets whose
     independence is contested (HK01, 星島/Sing Tao, sina): fine for a plain
     local fact that corroborates a better source, but not the sole or lead
     source for a contested or political claim. Are images freely-licensed,
     self-hosted under `vault/assets`, and attributed (never hotlinked
     news-agency photos)?
5. **Content scouting — lineage first, then relevance.** For each core topic
   search roughly the last 7–10 days for developments (rulings, sentencings,
   arrests, closures, new films/reports/collections, significant analysis).
   **Before flagging an item as missing, grep the vault to confirm it isn't
   already covered.** Then sort every genuine candidate into two buckets:
   - **🧬 Lineage (priority).** The development *continues a thread the
     archive already tells* — a person, case, outlet, event or site that
     already has a page or a section (e.g. a new sentencing for someone on
     `faces-of-the-crackdown`, a fresh ruling in `hong-kong-47`, a fire-case
     development, a press-freedom closure). These almost always belong in the
     archive; name the exact target page/section to extend.
   - **🔗 Relevance (judgement).** Genuinely new but adjacent — a story that
     fits the archive's mission but has no existing thread yet. Flag it with a
     recommendation: fold into an existing hub, open a new page/section, or
     add to the watchlist and wait for it to develop.
   Every candidate carries **source(s)** per the step-4 sourcing rules.
6. **Deliver to the Claude Doc** — maintain one living doc titled
   "SHKO Weekly Health Check"; prepend a new `## YYYY-MM-DD` section holding
   the digest, ranked 🔴 must-fix / 🟡 should-update / 🟢 nice-to-have, with
   lineage items ahead of relevance-only ones inside 🟡, plus a
   Watchlist-status line. Mechanical fixes are a checklist for a maintainer.
7. **Notify** — send a push notification with the doc link and severity counts.

## Core topics

background · book-censorship · faces-of-the-crackdown (+ person pages) ·
films · glory-to-hong-kong · hong-kong-47 · hong-kong-fire-2025 (+ subpages)
· press-freedom · statues · tiananmen-vigil · the Alliance / 8964 · the
preserved-sites index.

## Known pending events to watch

Keep these from going stale — update the relevant page when they land:

- **Pillar of Shame** confiscation ruling (separate routine already watches `statues.md`).
- **Wang Fuk Court fire** independent committee **redacted public report** — the full report was submitted to the CE on 22 Oct 2026; a redacted version is due the following week. Watch for its release and the government's reform/accountability plans.
- **Jason Kong** (fire petition organiser) fraud trial.
- **Ronson Chan** — Court of Final Appeal leave application on his obstruction conviction.
- **Jimmy Lai** — NSL trial verdict / sentencing.
- **Joshua Wong** — sentencing on the second (foreign-collusion) charge.
- **EU** — whether the Council acts on the Parliament's sanctions call (the Parliament's resolution is already recorded on `sites.hka`).

## Improving it over time

Candidate upgrades: a persistent watchlist so the scout only surfaces
genuinely new items; per-topic parallel review agents; and automated
external-link and image liveness checks (step 4 currently relies on the
agent spot-checking). Delivery stays as a read-only report to the Claude
Doc — fixes are applied here in a local checkout, by design.
