/**
 * The DOM-free core of the embeddable badge (#144): fetch → read → integrity → optional origin →
 * §AA view. Kept separate from the custom-element shell so the deterministic logic typechecks under
 * the base (DOM-free) tsconfig and is unit-tested in node - the honesty-critical part carries no DOM
 * dependency. Reuses the openom-js read/verify path verbatim; zero inference.
 */
import { readPayloadFromBytes } from "../src/read.js";
import {
  verifyOrigin,
  canonicalMirrorUrl,
  type MirrorFetch,
  type OriginResult,
} from "../src/origin.js";
import { badgeState, honestLabel, FORBIDDEN, type BadgeState } from "../src/badge.js";
import { classifyStale } from "../src/stale.js";
import { payloadHash } from "../src/hash.js";

export interface BadgeView {
  state: BadgeState;
  label: string;
  caption: string;
  /** A11y text; empty for `absent` (the element renders nothing). */
  ariaLabel: string;
  /** Invariant guard: the chosen label/caption must not overclaim for integrity-only. */
  honest: boolean;
  /** Set when the domain mirror carries a NEWER assertion than the embedded payload (OMW-W051): the
   * PDF is stale/superseded. The badge stays (it is genuine), but the reader should be told ([M2]). */
  stale?: "OMW-W051";
  /** The mirror's assertedDate, when stale - "a newer version dated …". */
  mirrorAssertedDate?: string;
  /** [M8] Set when the same-domain mirror is reachable but serves DIFFERENT content that is not a
   * supersede (edited/wrong figures): the source-of-truth disagrees with this copy (OMW-W052). */
  diverged?: "OMW-W052";
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

/**
 * [B1] Render a badge from a PRECOMPUTED state, with NO fetch. A portal that ran om_read once at ingest
 * (server-side) stores the state and emits `<openom-badge state="integrity-ok">` on its list pages, so
 * a results grid of N listings costs zero client PDF downloads. Honesty is preserved: the label/caption
 * come only from honestLabel, and an unknown/absent state renders nothing.
 */
export function viewForState(state: string): BadgeView {
  const known: BadgeState[] = [
    "absent",
    "hash-mismatch",
    "integrity-ok",
    "origin-verified",
    "signature-verified",
  ];
  const s = (known as string[]).includes(state) ? (state as BadgeState) : "absent";
  const { label, caption } = honestLabel(s);
  const overclaims =
    s === "integrity-ok" &&
    FORBIDDEN.some((w) => (label + " " + caption).toLowerCase().includes(w));
  return {
    state: s,
    label,
    caption,
    ariaLabel: s === "absent" ? "" : `openOM: ${label}. ${caption}`,
    honest: !overclaims,
  };
}

// [B1] Module-level result cache keyed by src|mirror, so N badges pointing at the same PDF (or a
// re-render) never re-download it. Stores the in-flight promise (dedupes concurrent evaluates too).
const _evalCache = new Map<string, Promise<BadgeView>>();
// [#2] bound the cache so a long-lived page badging many distinct URLs can't grow it without limit.
// Map preserves insertion order, so evicting the first key is a simple FIFO cap.
let _evalCacheMax = 512;

/** Tune the badge result-cache cap (default 512). Also the test hook for the eviction path ([#2]). */
export function setBadgeCacheMax(n: number): void {
  _evalCacheMax = Math.max(1, Math.floor(n));
}

/** Current number of cached badge results (observability). */
export function badgeCacheSize(): number {
  return _evalCache.size;
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

/**
 * Run the full read→verify pipeline and return the view. Deterministic; no inference. [B1] Result is
 * cached by src|mirror so repeated/duplicate badges for the same PDF fetch once. Pass a `fetchImpl`
 * (tests / a custom fetcher) to bypass the cache implicitly-not - the cache key ignores fetchImpl, so
 * tests that need a fresh run should vary src or call `clearBadgeCache()`.
 */
export function evaluateBadge(opts: BadgeOptions): Promise<BadgeView> {
  const key = `${opts.src}|${opts.mirror ?? ""}`;
  const hit = _evalCache.get(key);
  if (hit) return hit;
  const p = _evaluate(opts).catch((e) => {
    _evalCache.delete(key); // don't cache a transient failure
    throw e;
  });
  if (_evalCache.size >= _evalCacheMax) {
    const oldest = _evalCache.keys().next().value;
    if (oldest !== undefined) _evalCache.delete(oldest);
  }
  _evalCache.set(key, p);
  return p;
}

/** Drop the badge result cache (tests, or a portal that knows a PDF changed). */
export function clearBadgeCache(): void {
  _evalCache.clear();
}

async function _evaluate(opts: BadgeOptions): Promise<BadgeView> {
  const f = opts.fetchImpl ?? fetch;
  const read = await readPayloadFromBytes(await bytesOf(opts.src, f));
  if (read.state === "absent" || read.state === "encrypted") return computeBadge(ABSENT);

  // [M1] Discover the mirror: an explicit opts.mirror wins, else the payload's own meta.canonicalUrl -
  // so origin-verification + staleness are reachable from the bytes alone, with no per-listing config.
  const mirrorUrl = opts.mirror ?? canonicalMirrorUrl(read.payload);
  let originVerified = false;
  let originReason: OriginResult["reason"] | null = null;
  let mirrorBody: Uint8Array | null = null;
  if (mirrorUrl && read.payloadHash) {
    const fetchMirror: MirrorFetch = async (url) => {
      try {
        const res = await f(url);
        if (!res.ok) return null;
        const body = new Uint8Array(await res.arrayBuffer());
        mirrorBody = body; // keep for the staleness check below
        return { https: new URL(res.url || url).protocol === "https:", body };
      } catch {
        return null;
      }
    };
    const o = await verifyOrigin({
      sourceUrl: opts.src,
      mirrorUrl,
      embeddedHash: read.payloadHash,
      fetchMirror,
    });
    originVerified = o.originVerified;
    originReason = o.reason;
  }

  const view = computeBadge({
    present: true,
    hashValid: read.verification.hashValid,
    originVerified,
    signatureValid: read.verification.signatureValid,
  });

  // [M2] If the domain mirror carries a NEWER assertion than the embedded payload, mark it stale so
  // the reader isn't shown a confident badge on a superseded deal (OMW-W051). Only when we have a
  // mirror body AND our own payload; a genuine mismatch (not a supersede) is left to the badge state.
  if (mirrorBody && read.payload && read.payloadHash) {
    try {
      const mirrorPayload = JSON.parse(new TextDecoder().decode(mirrorBody)) as Record<
        string,
        unknown
      >;
      const s = classifyStale({
        embeddedHash: read.payloadHash,
        mirrorHash: payloadHash(mirrorPayload),
        embeddedPayload: read.payload,
        mirrorPayload,
      });
      if (s.stale && s.code) {
        view.stale = s.code;
        if (s.mirrorAssertedDate) view.mirrorAssertedDate = s.mirrorAssertedDate;
      }
    } catch {
      /* malformed mirror → no stale claim */
    }
  }
  // [M8] The mirror is reachable + same-domain but serves DIFFERENT content that is NOT a supersede
  // (edited/wrong numbers): warn instead of a clean integrity pass. Never overrides hash-mismatch.
  if (originReason === "hash-mismatch" && !view.stale && view.state === "integrity-ok") {
    view.diverged = "OMW-W052";
  }
  return view;
}

/** Absent view - for fail-closed rendering (a fetch/parse error is not evidence of tampering). */
export function absentView(): BadgeView {
  return computeBadge(ABSENT);
}

/** Normalized read-by-URL result for the hosted /verify + /v/ tools. */
export interface UrlReadResult {
  state: string;
  payload: Record<string, unknown> | null;
  verification: {
    hashValid: boolean | null;
    signatureValid: boolean | null;
    originVerified: boolean | null;
  };
  /** [M1/M8] surfaced by the worker path when it verified a same-domain canonicalUrl mirror. */
  stale?: "OMW-W051";
  diverged?: "OMW-W052";
}

const DEFAULT_MCP_ENDPOINT = "https://mcp.openom.app/mcp";

/**
 * Read+verify a PDF by URL - single source for /verify and /v/ ([#1 dedup]). Tries a direct browser
 * fetch first (same-origin / CORS-enabled hosts - fast, no round-trip), then falls back to the public
 * MCP worker's om_read, which fetches server-side (following presigned/CDN redirects) and hash-verifies
 * deterministically, so cross-origin listing PDFs work without CORS or an extension. A non-https
 * fallback target throws locally (no pointless worker call). Zero inference. `fetchImpl`/`endpoint`
 * injected for tests.
 */
export async function readByUrl(
  url: string,
  opts: { fetchImpl?: typeof fetch; endpoint?: string } = {},
): Promise<UrlReadResult> {
  const f = opts.fetchImpl ?? fetch;
  try {
    const resp = await f(url);
    if (resp.ok) {
      const bytes = new Uint8Array(await resp.arrayBuffer());
      const r = await readPayloadFromBytes(bytes);
      return {
        state: r.state,
        payload: r.state === "present" ? r.payload : null,
        verification: {
          hashValid: r.verification.hashValid,
          signatureValid: r.verification.signatureValid,
          originVerified: null, // direct browser path can't fetch a cross-domain mirror (CORS)
        },
      };
    }
  } catch {
    /* CORS/network blocked - fall through to the worker */
  }
  // badge-core is DOM-free (base tsconfig has no DOM lib); reach the page base URL via globalThis.
  const base = (globalThis as { location?: { href?: string } }).location?.href;
  let abs: URL;
  try {
    abs = new URL(url, base);
  } catch {
    throw new Error("invalid URL");
  }
  if (abs.protocol !== "https:") throw new Error("only https URLs can be checked remotely");
  const resp = await f(opts.endpoint ?? DEFAULT_MCP_ENDPOINT, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name: "om_read", arguments: { url: abs.href } },
    }),
  });
  const j = (await resp.json()) as {
    error?: { message?: string };
    result?: { isError?: boolean; code?: string; content?: Array<{ text?: string }> };
  };
  if (j.error) throw new Error(j.error.message || "read failed");
  const rr = j.result ?? {};
  const text = rr.content?.[0]?.text;
  if (rr.isError) {
    // [M4] preserve the worker's stable machine code on the thrown error so a caller can branch on it.
    const err = new Error((text || "read failed").replace(/^Error:\s*/, "")) as Error & {
      code?: string;
    };
    if (typeof rr.code === "string") err.code = rr.code;
    throw err;
  }
  if (!text) throw new Error("empty response");
  const d = JSON.parse(text) as {
    state: string;
    payload: Record<string, unknown> | null;
    verification?: {
      hashValid?: boolean | null;
      signatureValid?: boolean | null;
      originVerified?: boolean | null;
    };
    stale?: "OMW-W051";
    diverged?: "OMW-W052";
  };
  const out: UrlReadResult = {
    state: d.state,
    payload: d.payload,
    verification: {
      hashValid: d.verification?.hashValid ?? null,
      signatureValid: d.verification?.signatureValid ?? null,
      originVerified: d.verification?.originVerified ?? null,
    },
  };
  if (d.stale) out.stale = d.stale;
  if (d.diverged) out.diverged = d.diverged;
  return out;
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
