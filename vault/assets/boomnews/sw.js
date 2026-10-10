// ReplayWeb.page service worker (must be served same-origin as replay.html).
// It simply loads the upstream worker from the CDN.
importScripts("https://cdn.jsdelivr.net/npm/replaywebpage/sw.js");
