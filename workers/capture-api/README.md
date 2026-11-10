# shko capture-API Worker (#40 / #41)

Tier-0 on-demand page capture on **Cloudflare Browser Run** (managed headless
Chromium), storing a full-page screenshot + rendered HTML + a provenance record
to R2. It mirrors `scripts/capture_page.py` — including the **same
challenge-page detection**, so a bot-wall is reported, never stored as the
archive. See `reports/capture-pipeline.md` for the whole design.

This Worker is the **cloud variant for cooperative (Tier-0) sites only**.
Bot-walled (Tier-1) and authenticated (Tier-2) captures stay on the local /
residential path (`capture_page.py`, Browsertrix) — do not route cookies or
hostile sites here (#43).

## Use

```
curl -X POST https://shko-capture-api.<subdomain>.workers.dev/ \
  -H 'content-type: application/json' \
  -d '{"url":"https://hongkongfp.com/","name":"hkfp"}'
```

Response is the provenance record (`status` = `ok` | `blocked` | `dead`); on
`ok` the PNG/HTML/JSON are written under `screenshots/<name>/<ts>.*` in the
`shko-public` bucket.

## Deploy

Requires an account on **Workers Paid** (Browser Run) and `wrangler` with
credentials. The in-session Cloudflare **Workers Bindings MCP connector cannot
deploy Worker code** — use one of:

- a `CLOUDFLARE_API_TOKEN` scoped for **Workers Scripts: Edit**, **Browser
  Rendering**, **Workers R2 Storage**, then:
  ```
  cd workers/capture-api
  npm install
  CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... npx wrangler deploy
  ```
- or the newer full-API MCP server at `https://mcp.cloudflare.com/mcp`.

Local equivalent (no Cloudflare, same behaviour/classification) while a deploy
path is unavailable:

```
python3 scripts/capture_page.py https://hongkongfp.com/ --name hkfp --out captures
```

## Bindings (`wrangler.toml`)

- `BROWSER` — Browser Rendering binding.
- `ARCHIVE` — R2 bucket `shko-public` (shareable Tier-0 captures only).
