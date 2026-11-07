
Parent: [[Participation|participation]]

This archive is a living record, and so is the way it's built. As collections grow, pages are restructured for clarity — and because the whole project is open, we keep that work in the open too. This **design log** notes each significant overhaul: what changed, why, and what it looked like before and after. "Before" screenshots of the affected pages are preserved in our own storage, so the prior design isn't lost when a page is rewritten.

---

## 2026-10 — Hong Kong Fire 2025 collection restructuring

**Status:** structure done 31 Oct 2026; de-duplication pass 2 Nov 2026 · Milestone [HK Fire collection restructuring](https://github.com/China-Digital-Times-CDT/wepreserve/milestone/3) · Tracking issue [#30](https://github.com/China-Digital-Times-CDT/wepreserve/issues/30)

**Why.** The [[🔥 Hong Kong Fire 2025|hong-kong-fire-2025]] collection grew into the archive's largest, and parts became hard to scan. A measurement on 30 Oct 2026:

| Page | Words | Worst single block | |
|---|---:|---:|---|
| hub | 2,231 | **1,116-word** "Status snapshot" paragraph | landing page was a wall of text |
| investigation | 5,841 | **3,217-word** block (7 headings) | under-sectioned |
| activism | 3,154 | 1,541-word block | under-sectioned |
| people | 3,972 | 858 | ok |
| timeline | 3,900 | 710 (phased tables) | fine |
| report | 1,678 | 114 (clean `##` sections) | the model to follow |

**The plan.**
- Turn the **hub** into a scannable landing page — short lead + an "At a glance" status table — and push narrative detail down to the subpages where it already lives.
- Split **resettlement / buyback / homeowners' meeting** into its own subpage (it was smeared across the hub).
- Break the **investigation** and **activism** walls of text into dated sub-sections, following the `report` page's pattern.
- De-duplicate so each fact lives in one place, with the hub linking out.

**Before (captured 30 Oct 2026).** Full-page snapshots of every page as it stood before the overhaul:

- [Hub](https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/design-log/hong-kong-fire-2025/2026-10-30-before/hub.png)
- [Timeline](https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/design-log/hong-kong-fire-2025/2026-10-30-before/timeline.png)
- [Investigation](https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/design-log/hong-kong-fire-2025/2026-10-30-before/investigation.png)
- [Report](https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/design-log/hong-kong-fire-2025/2026-10-30-before/report.png)
- [Activism](https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/design-log/hong-kong-fire-2025/2026-10-30-before/activism.png)
- [People](https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/design-log/hong-kong-fire-2025/2026-10-30-before/people.png)

**After (completed 31 Oct 2026).** The hub is now a scannable landing page, resettlement has its own subpage, and the two walls of text are broken into sections. The structure linter reports zero broken links, frontmatter or convention issues.

How the same measurement looks after the overhaul (words / largest contiguous block between headings):

| Page | Before | After |
|---|---|---|
| hub | 2,231 w · **1,116**-word block | **833** w · 234 |
| investigation | 5,841 w · **3,217** (7 headings) | 6,017 w · **1,297** |
| activism | 3,154 w · **1,541** | 2,898 w · 1,254 |
| report | 1,678 w · 114 | 2,563 w · 561 |
| timeline | 3,900 w · 710 | 3,931 w · 795 |
| people | 3,972 w · 858 | 4,042 w · 923 |
| resettlement | — | 896 w · 315 *(new page)* |

The "after" figures count the words between any two headings, so adding sub-headings lowers them by itself. The "before" figures were measured on 30 Oct with a method that was not recorded, so treat the comparison as approximate.

Total word counts did **not** fall. Several pages grew, because the same weeks brought the final report, the 259 Buildings Department charges, Winnie Ho's resignation and the demands for more. The aim was scannability, not deletion. One regression dropped records mid-overhaul; it was caught and the content restored (commits `d95d44e`, `620c72a`). Details trimmed from one investigation bullet were later moved to the resettlement page.

What changed:
- **Hub → landing page**: a short lead, the report callout, an **"At a glance"** status table (one row per topic), a slim Key Facts, and an annotated **"Explore the collection"** router. Its largest block fell from a 1,116-word "Status snapshot" paragraph to 234 words.
- **New subpage** [[Resettlement & Owners|hong-kong-fire-2025.resettlement]]: the buyback, the 17 holdouts, rehousing and the homeowners'-meeting fight.
- **Sectioning**: the investigation page now has `##` / `###` / `####` headings throughout. Activism has `##` and `###` sections; its largest block is now 791 words.

**De-duplication (2 Nov 2026).** After the first pass, the hearings, the June charges and the October report still appeared at length on both the timeline and the investigation page. Six long timeline rows are now one-line dated entries that link to the page holding the full account. Any detail that existed only on the timeline was moved to that page first: the 31 August buyback figures to resettlement, the Competition Commission's bid-rigging plan to investigation, and the 22 October submission to the report page. A script compared every source link and figure across the fire pages before and after, and none was lost. Every block in the collection is now under 1,000 words. What remains by design: the timeline keeps a short dated line for each event, the hub keeps its At-a-glance summary, and people profiles mention the events they took part in.

Samples captured 31 Oct 2026, showing the top 2,600 px of each page rather than the full page:

- [Hub](https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/design-log/hong-kong-fire-2025/2026-10-31-after/hub.png)
- [Investigation](https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/design-log/hong-kong-fire-2025/2026-10-31-after/investigation.png)
- [Resettlement](https://pub-24ab8cd7de4a4b2fa258f19bdf31e115.r2.dev/design-log/hong-kong-fire-2025/2026-10-31-after/resettlement.png)
