/* eslint-disable */
// SHKO override: replace the template's Giscus (Discussions) widget with an
// Utterances comment box backed by GitHub Issues, shown site-wide on every
// note. One issue is created per page (issue-term="pathname"). A short safety
// reminder is rendered above the box because this archive holds politically
// sensitive material. Requires the utterances GitHub App to be installed on
// the repo (https://github.com/apps/utterances).
import React, { useEffect, useRef } from "react";
import { useRouter } from "next/router";

const REPO = "China-Digital-Times-CDT/wepreserve";

export const DendronNoteGiscusWidget = (_props: { note?: any; config?: any }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    // Clear any previous instance (e.g. on client-side navigation between notes).
    container.innerHTML = "";
    const script = document.createElement("script");
    script.src = "https://utteranc.es/client.js";
    script.async = true;
    script.crossOrigin = "anonymous";
    script.setAttribute("repo", REPO);
    script.setAttribute("issue-term", "pathname");
    script.setAttribute("label", "comment");
    script.setAttribute("theme", "preferred-color-scheme");
    container.appendChild(script);
  }, [router.asPath]);

  return (
    <section
      className="shko-comments"
      style={{
        marginTop: "2.5rem",
        paddingTop: "1.25rem",
        borderTop: "1px solid rgba(128,128,128,0.25)",
      }}
    >
      <h2 style={{ fontSize: "1.2rem", marginBottom: "0.4rem" }}>
        Comments · 留言
      </h2>
      <p
        style={{
          fontSize: "0.85em",
          color: "#888",
          lineHeight: 1.55,
          margin: "0 0 1rem",
        }}
      >
        Comments are public and powered by GitHub Issues (via{" "}
        <a href="https://utteranc.es/" target="_blank" rel="noopener noreferrer">
          utterances
        </a>
        ); a GitHub login is required to post.{" "}
        <strong>Please think about your safety first.</strong> This archive holds
        politically sensitive material. Anything you write here is permanently
        public and tied to your GitHub account — do not post information that
        could identify you, your family, or others at risk. To share something
        privately instead, see{" "}
        <a href="/notes/vzihkvznemcaaef2br0s1co/">Participation</a>.
      </p>
      <div ref={containerRef} />
    </section>
  );
};
