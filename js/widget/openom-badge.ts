/**
 * `<openom-badge>` — a web-embeddable trust badge for portals (#144).
 *
 * A portal drops one script tag and `<openom-badge src="…deal.pdf">` next to a listing; the widget
 * re-fetches the PDF bytes, reads + integrity-checks the embedded openOM payload, optionally verifies
 * origin against a mirror, and renders the §AA badge. The verification is the exact deterministic,
 * inference-free openom-js read/verify path the extension uses (see ./badge-core) — never
 * re-implemented — so a portal badge and the browser badge can never disagree.
 *
 * Honesty is load-bearing (§AA / [OM-TRUST-003]): the label comes ONLY from `honestLabel`, and
 * `absent` renders nothing (no false reassurance, no nag on the majority of PDFs that aren't openOM).
 * No payload-derived text is injected into the DOM, so an attacker-controlled payload has no XSS
 * surface — the only dynamic string is the sanitized `details` href.
 *
 * This file is the DOM shell; build it via widget/build.mjs and typecheck it via tsconfig.widget.json
 * (it needs the DOM lib the deterministic core deliberately excludes).
 */
import { evaluateBadge, absentView, sanitizeHref, type BadgeView } from "./badge-core.js";
import type { BadgeState } from "../src/badge.js";

const PALETTE: Record<BadgeState, { fg: string; bg: string; mark: string }> = {
  absent: { fg: "", bg: "", mark: "" },
  "hash-mismatch": { fg: "#7f1d1d", bg: "#fef2f2", mark: "⚠" },
  "integrity-ok": { fg: "#374151", bg: "#f3f4f6", mark: "✓" },
  "origin-verified": { fg: "#065f46", bg: "#ecfdf5", mark: "✓✓" },
  "signature-verified": { fg: "#065f46", bg: "#ecfdf5", mark: "✓✓" },
};

/** Render a computed view into a shadow root under `host`. Absent → cleared (renders nothing). */
export function paintBadge(host: HTMLElement, view: BadgeView, details?: string): void {
  const root = host.shadowRoot ?? host.attachShadow({ mode: "open" });
  if (view.state === "absent") {
    root.replaceChildren();
    return;
  }
  const c = PALETTE[view.state];
  const link = sanitizeHref(details);
  const wrap = document.createElement("span");
  wrap.setAttribute("role", "img");
  wrap.setAttribute("aria-label", view.ariaLabel);
  wrap.title = view.caption;
  wrap.style.cssText =
    `display:inline-flex;align-items:center;gap:.4em;font:600 13px/1.4 system-ui,sans-serif;` +
    `padding:.25em .6em;border-radius:999px;color:${c.fg};background:${c.bg};` +
    `border:1px solid ${c.fg}22;`;
  const mark = document.createElement("span");
  mark.textContent = c.mark;
  mark.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.textContent = view.label; // static honestLabel copy only — no payload text
  wrap.append(mark, label);
  if (link) {
    const a = document.createElement("a");
    a.href = link;
    a.textContent = "details";
    a.rel = "noopener noreferrer";
    a.style.cssText = `color:inherit;opacity:.7;font-weight:400;text-decoration:underline;`;
    wrap.append(a);
  }
  root.replaceChildren(wrap);
}

/** The custom element. Reflects `src`/`mirror`/`details`; re-evaluates on attribute change. */
export class OpenOmBadgeElement extends HTMLElement {
  static get observedAttributes(): string[] {
    return ["src", "mirror", "details"];
  }
  connectedCallback(): void {
    void this.refresh();
  }
  attributeChangedCallback(): void {
    if (this.isConnected) void this.refresh();
  }
  async refresh(): Promise<void> {
    const src = this.getAttribute("src");
    if (!src) return;
    const details = this.getAttribute("details") ?? undefined;
    const mirror = this.getAttribute("mirror");
    try {
      const view = await evaluateBadge(mirror ? { src, mirror } : { src });
      paintBadge(this, view, details);
    } catch {
      // A fetch/parse failure is not evidence of tampering: fail closed to "absent" (render nothing)
      // rather than show a scary state the bytes don't justify (§AA honesty).
      paintBadge(this, absentView());
    }
  }
}

/** Register `<openom-badge>` once. Safe to call repeatedly (idempotent). */
export function defineOpenOmBadge(tag = "openom-badge"): void {
  if (typeof customElements !== "undefined" && !customElements.get(tag)) {
    customElements.define(tag, OpenOmBadgeElement);
  }
}

// Auto-register when loaded as a browser script (the embed use case).
if (typeof document !== "undefined") defineOpenOmBadge();
