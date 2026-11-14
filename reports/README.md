# Weekly archive health check

Automated weekly review of the SHKO archive. A cloud routine runs every
**Monday 08:00 Hong Kong time** and reports a dated digest as its **run
output** (plus a push notification) — it publishes nothing, so nothing piles
up. The digest is pulled into a working session and acted on there (see the
Delivery note).

**Delivery note.** This is a **read-only reviewer by design**. The cloud
routine clones and reads `main` but never writes to the repo — it does
**not** commit, push, or open PRs, and it must not try. Edits to the archive
are made **here**, in a normal local checkout, and pushed to `main`
directly (CI rebuilds the live site); the Claude GitHub App is not part of
that path.

**The routine does NOT publish anything** (no Claude Doc, no artifact — an
earlier version piled a new section into a doc nobody read each week). It
just **reports**: the full digest is its **final run message**, plus a short
push notification with the counts. To act on it, pull the latest run's digest
into a working session (`RemoteTrigger` → `list_runs` then `get_run_log` on
`trig_012tTw8jyryo5sg4YkryUYew`), evaluate it together, and apply fixes
locally. Because the check re-scans the live repo each week and greps before
flagging, **the latest run is always the current truth** — nothing
accumulates, and fixed items simply stop appearing. (This directory keeps the
recipe and any manually-saved reports.)

## What the weekly check does (v2)

The check has three parts: an **audit** of the archive as it stands (steps
2–4), a **scout** for content worth editing in (step 5), and a
**live-issues review** that walks the continuously-watched topics and
promotes matured proposals (step 5b — see [Live issues](#live-issues)).

1. **Read latest `main`** (read-only; never push).
2. **Deterministic checks** — run `python3 scripts/check_archive.py`:
   broken wikilinks (incl. reversed `[[Alias|target]]` order and case
   mismatches), missing frontmatter, stale "due/expected <Month YYYY>" lines
   whose date has passed, hub pages missing a Sources/香港中文報道 block,
   and orphan pages. It **also** reports **📸 screenshot-archive freshness**
   (#44) from the committed `reports/screenshot-index.json` — per curated site:
   fresh / 🟡 stale (no snapshot in >40 days — the monthly capture may have
   lapsed) / 🟠 residential-pending (e.g. hkja, needs a residential-IP run) /
   ⚫ gone (a `retired` site that went off the grid — final snapshot kept, **not
   traced further**, never flagged stale). Surface stale/pending in the digest.
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
   - **5b. Live-issues review.** The archive's continuously-watched topics
     are tracked as GitHub issues carrying the **`live`** label (see
     [Live issues](#live-issues) for the full convention). Fetch the open
     live issues
     (`https://api.github.com/repos/China-Digital-Times-CDT/wepreserve/issues?state=open&labels=live&per_page=100`,
     unauthenticated read is fine for this public repo). For **each** live
     issue — it names its vault page and its watch routine — grep the vault
     for what already exists and research the last ~1–2 weeks for
     developments, then classify it as exactly one of: **🆕 new** (a sourced
     development since last review — name the exact page/section to extend and
     the source), **🔭 now retrospectable** (the thread has settled — a
     deepening research pass is due; name the gaps, and for an `active-watch`
     item note its cloud routine can now be disabled), **⏸ no change**
     (nothing material this week), or **✅ mature** (the page is comprehensive
     and only needs the weekly check — the issue can be closed). Then,
     *separately*, scan the remaining open issues that do **not** carry `live`
     but propose a new hub/page or a long-running collection: if one has now
     accumulated enough material to earn a page (a second case, a landed
     ruling, a cluster of titles), flag it **▶ promote** — recommend adding
     the `live` label and building, naming the material that justifies it;
     otherwise leave it waiting. Purely mechanical issues (a CI bug, a one-off
     fix) are out of scope. The point is to let topics mature on their own
     cadence and act only when one has earned the work.
6. **Report the digest as the run's final message** — do NOT publish or
   update any Claude Doc or artifact. Rank it 🔴 must-fix / 🟡 should-update /
   🟢 nice-to-have, with lineage items ahead of relevance-only ones inside 🟡,
   plus a **📋 Live-issues review** section (one line per `live` issue:
   `#<n> <title> — 🆕 new / 🔭 retrospectable / ⏸ no change / ✅ mature`, with
   the one-line reason and any new material; 🆕 and 🔭 first, then any
   ▶ promote) and a Watchlist-status line. Must-fix items
   are checklist lines a maintainer applies locally. The digest is read back
   from the run's output (see the Delivery note).
7. **Notify** — send one concise push notification with the severity counts
   and a one-line headline per 🔴/🟡 item (no doc link — there is no doc).

## Live issues

A **live issue** is a GitHub issue that tracks a topic the archive is
*actively watching and growing* — not a task that closes when a unit of work
is done, but a standing thread the weekly cycle (step 5b) reviews. This is how
pages improve on a cadence: each live issue asks, every Monday, *what's new?*
and *is this now settled enough to deepen?*

**The convention:**

- Label the issue **`live`**. It stays **open by design**; it closes only when
  the page is mature (then only the weekly audit tends it).
- Add exactly one **status** sub-label:
  - **`active-watch`** 🔴 — fast-moving; a cloud routine is appending to its
    page (M+/culture, the fire anniversary, the Pillar ruling). The issue
    records the routine id so it can be disabled when the story resolves.
  - **`growing`** 🟡 — being built out from research/submissions (the banned-
    books registry, the Cantonese collection). Matures as material accrues.
  - **`retrospectable`** 🔭 — the event has settled; the next move is a
    *deepening research pass* to make the page comprehensive (Joshua Wong,
    after sentencing became final). Its watch routine, if any, is disabled.
- The body links the issue's **vault page**, its **watch routine** (if any),
  and its **captured evidence** (R2 keys), plus *what each cycle checks* and
  *when it closes*.
- **Umbrella / independent.** A collection with several threads is an umbrella
  live issue with a task-list of sub-watches (e.g. *Fire 2025* → anniversary,
  criminal case, full report); a standalone topic is an independent live issue.

**The lifecycle:** a plain proposal issue → (enough material accrues) → the
weekly review flags **▶ promote**, it gains `live` + `growing` and a page is
built → **`active-watch`** while a routine or the news cycle feeds it →
**`retrospectable`** once it settles, for a deepening pass → **closed** when
the page is mature. The registry at any moment is
`gh issue list --label live`.

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
- **Jimmy Lai** — NSL trial verdict / sentencing.
- **Margaret Ng / Bar Association** — High Court judgment on the Bar ExCo's judicial review (HCAL1407/2026) seeking to overturn the tribunal that cleared her; heard 9 Nov 2026, reserved (within 6 months). See issue #39.
- **EU** — whether the Council acts on the Parliament's sanctions call (the Parliament's resolution is already recorded on `sites.hka`).
- *(Resolved — recorded, kept here briefly so the scout doesn't re-flag them): Joshua Wong second-charge sentencing = 10 years, 5 Nov 2026, on `faces-of-the-crackdown.joshua-wong`. Ronson Chan CFA leave refused 6 Nov 2026, on `sites.hkja`.)*

## Improving it over time

Candidate upgrades: a persistent watchlist so the scout only surfaces
genuinely new items; per-topic parallel review agents; and automated
external-link and image liveness checks (step 4 currently relies on the
agent spot-checking). Delivery stays as a read-only report to the Claude
Doc — fixes are applied here in a local checkout, by design.
