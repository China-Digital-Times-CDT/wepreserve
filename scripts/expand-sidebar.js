#!/usr/bin/env node
/**
 * Post-publish helper to auto-expand the Ant Design tree sidebar in the
 * Dendron static site (GitHub Pages).
 *
 * Run after `dendron publish` so the generated `main-*.js` bundle gets the
 * sidebar-expansion hook injected.
 */
const fs = require("fs");
const path = require("path");

const CHUNKS_DIR = path.join(__dirname, "..", "docs", "_next", "static", "chunks");
const SNIPPET = `
// Custom: auto-expand sidebar tree on load for GitHub Pages build
(()=>{const expandAll=()=>{document.querySelectorAll(".ant-tree-switcher_close").forEach(btn=>btn.click())};const attach=()=>{expandAll();const tree=document.querySelector(".ant-tree");if(tree){const obs=new MutationObserver(()=>expandAll());obs.observe(tree,{childList:!0,subtree:!0})}};if(document.readyState==="complete"||document.readyState==="interactive"){setTimeout(attach,50);}else{document.addEventListener("DOMContentLoaded",()=>setTimeout(attach,50));}})();
`;

function main() {
  if (!fs.existsSync(CHUNKS_DIR)) {
    console.error("Sidebar patch skipped: chunks dir not found:", CHUNKS_DIR);
    process.exitCode = 1;
    return;
  }

  const mainChunk = fs
    .readdirSync(CHUNKS_DIR)
    .find((name) => name.startsWith("main-") && name.endsWith(".js"));

  if (!mainChunk) {
    console.error("Sidebar patch skipped: no main-*.js chunk found in", CHUNKS_DIR);
    process.exitCode = 1;
    return;
  }

  const chunkPath = path.join(CHUNKS_DIR, mainChunk);
  const content = fs.readFileSync(chunkPath, "utf8");

  if (content.includes("auto-expand sidebar tree")) {
    console.log("Sidebar patch already present in", mainChunk);
    return;
  }

  fs.writeFileSync(chunkPath, content + "\n" + SNIPPET, "utf8");
  console.log("Sidebar patch appended to", mainChunk);
}

main();
