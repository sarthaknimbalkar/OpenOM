// The injected link-badge pill (#69). A PURE function of the verified badge state — content scripts
// can't load popup.css, so styles are inline design-token hex values. §AA UI-honesty: it claims ONLY
// the verified state, and `absent`/`encrypted`/`signature-verified` produce NO marker (never mark a
// non-openOM / unreadable PDF). Type-only BadgeState import → erased, so this file adds no bundle weight.
import type { BadgeState } from "openom-js";

interface Style {
  text: string;
  color: string;
  label: string;
}

const STYLES: Partial<Record<BadgeState, Style>> = {
  "origin-verified": { text: "openOM ✓✓", color: "#0a5f2e", label: "openOM origin-verified" },
  "integrity-ok": { text: "openOM ✓", color: "#4b5160", label: "openOM data, unaltered since embed" },
  "hash-mismatch": { text: "⚠ altered", color: "#b3261e", label: "openOM data does not match its hash" },
};

/** Build the pill for a state, or null when there is nothing honest to claim. */
export function markerFor(state: BadgeState): HTMLElement | null {
  const s = STYLES[state];
  if (!s) return null;
  const el = document.createElement("span");
  el.setAttribute("data-openom-marker", "");
  el.setAttribute("data-state", state);
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", s.label);
  el.textContent = s.text;
  el.style.cssText = `display:inline-block;margin-left:4px;padding:0 5px;border-radius:6px;font:600 11px/1.6 system-ui,sans-serif;color:${s.color};background:#fbfaf5;border:1px solid ${s.color};vertical-align:baseline;`;
  return el;
}
