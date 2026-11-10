# On-demand WACZ crawler (#42).
#
# Browsertrix Crawler plus an env-driven entrypoint that crawls a seed and —
# via Browsertrix's built-in S3 upload — streams the resulting WACZ to
# Cloudflare R2. Runs as a one-shot container: locally via `docker run` (the
# path dogfooded 2026-11-10 to refresh The Witness), or on Cloudflare
# Containers on demand (idle-to-zero). See README.md.
FROM webrecorder/browsertrix-crawler:latest

COPY crawl.sh /usr/local/bin/crawl.sh
RUN chmod +x /usr/local/bin/crawl.sh

ENTRYPOINT ["/usr/local/bin/crawl.sh"]
