/**
 * `<openom-badge>` - a web-embeddable trust badge for portals (#144).
 *
 * A portal drops one script tag and `<openom-badge src="…deal.pdf">` next to a listing; the widget
 * re-fetches the PDF bytes, reads + integrity-checks the embedded openOM payload, optionally verifies
 * origin against a mirror, and renders the §AA badge. The verification is the exact deterministic,
 * inference-free openom-js read/verify path the extension uses (see ./badge-core) - never
 * re-implemented - so a portal badge and the browser badge can never disagree.
 *
 * Honesty is load-bearing (§AA / [OM-TRUST-003]): the label comes ONLY from `honestLabel`, and
 * `absent` renders nothing (no false reassurance, no nag on the majority of PDFs that aren't openOM).
 * No payload-derived text is injected into the DOM, so an attacker-controlled payload has no XSS
 * surface - the only dynamic string is the sanitized `details` href.
 *
 * This file is the DOM shell; build it via widget/build.mjs and typecheck it via tsconfig.widget.json
 * (it needs the DOM lib the deterministic core deliberately excludes).
 */
import {
  evaluateBadge,
  computeBadge,
  viewForState,
  readByUrl,
  absentView,
  sanitizeHref,
  type BadgeView,
} from "./badge-core.js";
import { readPayloadFromBytes } from "../src/read.js";
import type { BadgeState } from "../src/badge.js";

declare global {
  interface Window {
    // Minimal global API for the hosted verify tool (a plain page can't import an IIFE's exports).
    openOM?: {
      evaluateBadge: typeof evaluateBadge;
      computeBadge: typeof computeBadge;
      readPayloadFromBytes: typeof readPayloadFromBytes;
      readByUrl: typeof readByUrl;
    };
  }
}

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
  wrap.setAttribute("part", "badge"); // [polish] host theming via ::part(badge) + the CSS vars below
  wrap.style.cssText =
    `display:inline-flex;align-items:center;gap:.4em;` +
    `font:var(--openom-badge-font, 600 13px/1.4 system-ui,sans-serif);` +
    `padding:.25em .6em;border-radius:var(--openom-badge-radius,999px);color:${c.fg};background:${c.bg};` +
    `border:1px solid ${c.fg}22;`;
  const mark = document.createElement("span");
  mark.textContent = c.mark;
  mark.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.textContent = view.label; // static honestLabel copy only - no payload text
  wrap.append(mark, label);
  if (view.stale) {
    // [M2] A superseded PDF: the badge is genuine but a newer assertion exists on the domain mirror.
    const stale = document.createElement("span");
    stale.textContent = view.mirrorAssertedDate
      ? `· superseded (newer dated ${view.mirrorAssertedDate})`
      : "· superseded — newer version available";
    stale.style.cssText = "font-weight:400;opacity:.85;";
    wrap.append(stale);
  }
  if (view.diverged) {
    // [M8] The source domain currently shows different figures than this copy - a strong warning.
    const diverged = document.createElement("span");
    diverged.textContent = "· source shows different data";
    diverged.style.cssText = "font-weight:600;color:#7a5b00;";
    wrap.append(diverged);
  }
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
  #io: IntersectionObserver | null = null;
  #lastKey: string | null = null; // [polish] src|mirror of the last evaluate, to skip a re-fetch
  #lastView: BadgeView | null = null; // cached view, repainted on a details-only change
  static get observedAttributes(): string[] {
    // [B1] `state` renders a precomputed badge with NO fetch (portals emit it from ingest-time om_read).
    return ["src", "mirror", "details", "state"];
  }
  connectedCallback(): void {
    // [B1] Precomputed state → paint immediately, never fetch. A src with no state → lazy-mount: only
    // fetch when scrolled into view, so a results grid of N badges doesn't download N PDFs on load.
    if (this.getAttribute("state")) {
      void this.refresh();
      return;
    }
    if (typeof IntersectionObserver !== "undefined" && this.getAttribute("src")) {
      this.#io = new IntersectionObserver((entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          this.#io?.disconnect();
          this.#io = null;
          void this.refresh();
        }
      });
      this.#io.observe(this);
      return;
    }
    void this.refresh();
  }
  disconnectedCallback(): void {
    this.#io?.disconnect();
    this.#io = null;
  }
  attributeChangedCallback(_name: string, oldV: string | null, newV: string | null): void {
    // Only re-run for a meaningful change; `details` alone repaints without a re-fetch (handled in refresh).
    if (this.isConnected && oldV !== newV) void this.refresh();
  }
  /** [polish] Notify the host after each evaluate/paint so it can log coverage or show its own fallback. */
  #emit(view: BadgeView, error = false): void {
    this.#lastView = view;
    // An async refresh() can resolve AFTER the element is removed (e.g. between tests); a notify hook
    // must never fire post-disconnect nor ever throw. Skip when detached, and construct the event
    // from THIS element's own document realm (window in a browser, jsdom's in tests) - the ambient
    // global CustomEvent can be Node's built-in, which jsdom's dispatchEvent rejects.
    const win = this.ownerDocument?.defaultView;
    if (!this.isConnected || !win) return;
    try {
      this.dispatchEvent(
        new win.CustomEvent("openom:state", {
          bubbles: true,
          detail: {
            state: view.state,
            present: view.state !== "absent",
            stale: view.stale ?? null,
            diverged: view.diverged ?? null,
            error,
          },
        }),
      );
    } catch {
      /* a notify hook must never break render or surface as an unhandled error */
    }
  }
  async refresh(): Promise<void> {
    const details = this.getAttribute("details") ?? undefined;
    const state = this.getAttribute("state");
    if (state) {
      // Zero-fetch precomputed render (honesty preserved: label/caption from honestLabel only).
      const v = viewForState(state);
      paintBadge(this, v, details);
      this.#emit(v);
      return;
    }
    const src = this.getAttribute("src");
    if (!src) return;
    const mirror = this.getAttribute("mirror");
    const key = `${src}|${mirror ?? ""}`;
    // [polish] a details-only change (src/mirror unchanged) repaints the cached view - never re-fetches.
    if (key === this.#lastKey && this.#lastView) {
      paintBadge(this, this.#lastView, details);
      return;
    }
    try {
      const view = await evaluateBadge(mirror ? { src, mirror } : { src });
      this.#lastKey = key;
      paintBadge(this, view, details);
      this.#emit(view);
    } catch {
      // A fetch/parse failure is not evidence of tampering: fail closed to "absent" (render nothing)
      // rather than show a scary state the bytes don't justify (§AA honesty).
      const v = absentView();
      paintBadge(this, v);
      this.#emit(v, true);
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

// Expose the read/verify primitives for the hosted verify tool (#145).
if (typeof window !== "undefined") {
  window.openOM = { evaluateBadge, computeBadge, readPayloadFromBytes, readByUrl };
}
