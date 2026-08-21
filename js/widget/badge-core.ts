/**
 * The DOM-free core of the embeddable badge (#144): fetch → read → integrity → optional origin →
 * §AA view. Kept separate from the custom-element shell so the deterministic logic typechecks under
 * the base (DOM-free) tsconfig and is unit-tested in node - the honesty-critical part carries no DOM
 * dependency. Reuses the openom-js read/verify path verbatim; zero inference.
 */
import { readPayloadFromBytes } from "../src/read.js";
import { verifyOrigin, type MirrorFetch } from "../src/origin.js";
import { badgeState, honestLabel, FORBIDDEN, type BadgeState } from "../src/badge.js";

export interface BadgeView {
  state: BadgeState;
  label: string;
  caption: string;
  /** A11y text; empty for `absent` (the element renders nothing). */
  ariaLabel: string;
  /** Invariant guard: the chosen label/caption must not overclaim for integrity-only. */
  honest: boolean;
}

/** Pure §AA state→view mapping. The honesty-critical core; DOM-free and fully unit-tested. */
export function computeBadge(v: {
  present: boolean;
  hashValid: boolean | null;
  originVerified: boolean;
  signatureValid: boolean | null;
}): BadgeView {
  const state = badgeState(v);
  const { label, caption } = honestLabel(state);
  // integrity-only must never borrow origin/signature vocabulary; verify it, don't just trust copy.
  const overclaims =
    state === "integrity-ok" &&
    FORBIDDEN.some((w) => (label + " " + caption).toLowerCase().includes(w));
  return {
    state,
    label,
    caption,
    ariaLabel: state === "absent" ? "" : `openOM: ${label}. ${caption}`,
    honest: !overclaims,
  };
}

export interface BadgeOptions {
  /** URL of the PDF to verify (re-fetched for bytes; never scraped from a viewer). */
  src: string;
  /** Optional mirror URL to attempt §10 origin verification (same registrable domain as src). */
  mirror?: string;
  /** Optional details link shown on the badge (sanitized to http/https). */
  details?: string;
  /** Injected for tests / non-browser hosts; defaults to global fetch. */
  fetchImpl?: typeof fetch;
}

const ABSENT = {
  present: false,
  hashValid: null,
  originVerified: false,
  signatureValid: null,
} as const;

async function bytesOf(url: string, f: typeof fetch): Promise<Uint8Array> {
  const res = await f(url);
  if (!res.ok) throw new Error(`fetch ${url}: ${res.status}`);
  return new Uint8Array(await res.arrayBuffer());
}

/** Run the full read→verify pipeline and return the view to render. Deterministic; no inference. */
export async function evaluateBadge(opts: BadgeOptions): Promise<BadgeView> {
  const f = opts.fetchImpl ?? fetch;
  const read = await readPayloadFromBytes(await bytesOf(opts.src, f));
  if (read.state === "absent" || read.state === "encrypted") return computeBadge(ABSENT);

  let originVerified = false;
  if (opts.mirror && read.payloadHash) {
    const fetchMirror: MirrorFetch = async (url) => {
      try {
        const res = await f(url);
        if (!res.ok) return null;
        return {
          https: new URL(res.url || url).protocol === "https:",
          body: new Uint8Array(await res.arrayBuffer()),
        };
      } catch {
        return null;
      }
    };
    const o = await verifyOrigin({
      sourceUrl: opts.src,
      mirrorUrl: opts.mirror,
      embeddedHash: read.payloadHash,
      fetchMirror,
    });
    originVerified = o.originVerified;
  }
  return computeBadge({
    present: true,
    hashValid: read.verification.hashValid,
    originVerified,
    signatureValid: read.verification.signatureValid,
  });
}

/** Absent view - for fail-closed rendering (a fetch/parse error is not evidence of tampering). */
export function absentView(): BadgeView {
  return computeBadge(ABSENT);
}

/** Sanitize a details href to http/https only (no javascript:/data: on an embedded widget). */
export function sanitizeHref(href: string | undefined): string | null {
  if (!href) return null;
  try {
    const u = new URL(href);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch {
    return null;
  }
}
