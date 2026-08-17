// openOM link-badging content script (#69) — THIN by design: DOM + IntersectionObserver + messaging
// only, no /js / tldts / pdf.js. The service worker does all openOM logic (eTLD+1 gating, verification
// via the deterministic detect pipeline + 24h cache). Runs on every https page but self-gates on the
// per-domain allowlist and exits immediately when not enabled. Verification is LAZY (on view),
// deduped, and hard-capped so it never hammers the page host or the user's network. Zero inference.
import { markerFor } from "./marker.js";
import type { BadgeState } from "openom-js";

const MAX_CONCURRENT = 3;
const MAX_PER_PAGE = 25;

async function install(): Promise<void> {
  if (!location.protocol.startsWith("https")) return;
  const res = (await chrome.runtime.sendMessage({ type: "linkbadge:enabled", hostname: location.hostname })) as {
    enabled?: boolean;
  };
  if (!res?.enabled) return; // not opted in for this domain — do nothing

  const seen = new Set<string>();
  const queue: HTMLAnchorElement[] = [];
  let inflight = 0;
  let done = 0;

  const candidateUrl = (a: HTMLAnchorElement): string | null => {
    try {
      const u = new URL(a.href);
      if (u.protocol !== "https:" || !u.pathname.toLowerCase().endsWith(".pdf")) return null;
      return u.href;
    } catch {
      return null;
    }
  };

  const observer = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const a = e.target as HTMLAnchorElement;
      observer.unobserve(a);
      if (done >= MAX_PER_PAGE) continue;
      queue.push(a);
    }
    pump();
  });

  const pump = (): void => {
    while (inflight < MAX_CONCURRENT && queue.length > 0 && done < MAX_PER_PAGE) {
      const a = queue.shift();
      if (!a) break;
      const url = candidateUrl(a);
      if (!url || seen.has(url)) continue;
      seen.add(url);
      inflight++;
      done++;
      chrome.runtime
        .sendMessage({ type: "linkbadge:verify", url })
        .then((r: { state?: BadgeState }) => {
          const m = r?.state ? markerFor(r.state) : null;
          if (m && a.isConnected && !a.nextElementSibling?.hasAttribute?.("data-openom-marker")) {
            a.insertAdjacentElement("afterend", m);
          }
        })
        .catch(() => {})
        .finally(() => {
          inflight--;
          pump();
        });
    }
  };

  const scan = (): void => {
    for (const a of document.querySelectorAll<HTMLAnchorElement>("a[href]")) {
      const url = candidateUrl(a);
      if (url && !seen.has(url)) observer.observe(a);
    }
  };

  // Re-scan for late/SPA links, throttled; still bounded by `seen` + the per-page cap.
  let pending = false;
  new MutationObserver(() => {
    if (pending) return;
    pending = true;
    setTimeout(() => {
      pending = false;
      scan();
    }, 500);
  }).observe(document.body, { childList: true, subtree: true });

  scan();
}

if (typeof chrome !== "undefined" && chrome.runtime?.id) void install();
