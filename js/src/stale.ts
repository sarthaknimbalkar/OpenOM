// Stale-vs-tamper (§AA [OM-TRUST-009], OMW-W051). When the embedded payload's hash differs from the
// origin mirror's CURRENT hash, decide whether the mirror is a genuine *newer* assertion (stale/
// superseded - surface a warning, keep the badge) or an actual mismatch (leave it to the badge).
// Single-sourced in openom-js so the extension service worker, the embeddable badge, and the /verify
// tool all decide staleness identically ([M2]). Pure + DOM-free.

export interface StaleResult {
  stale: boolean;
  code?: "OMW-W051";
  mirrorAssertedDate?: string;
}

function assertedDate(p: Record<string, unknown> | null): string | null {
  const d = p?.["assertedDate"];
  return typeof d === "string" ? d : null;
}

/** Parse an assertedDate to a comparable epoch, or null if it isn't a valid date (no silent skip). */
function parseDate(s: string | null): number | null {
  if (!s) return null;
  const t = Date.parse(s);
  return Number.isNaN(t) ? null : t;
}

function supersedes(p: Record<string, unknown> | null): string | null {
  const meta = p?.["meta"];
  if (meta && typeof meta === "object") {
    const s = (meta as Record<string, unknown>)["supersedes"];
    if (typeof s === "string") return s;
  }
  return null;
}

export function classifyStale(a: {
  embeddedHash: string;
  mirrorHash: string;
  embeddedPayload: Record<string, unknown>;
  mirrorPayload: Record<string, unknown> | null;
}): StaleResult {
  if (a.mirrorHash === a.embeddedHash) return { stale: false };

  // The mirror explicitly supersedes the embedded payload, or asserts strictly later → stale.
  const mirrorSupersedesUs = supersedes(a.mirrorPayload) === a.embeddedHash;
  const ours = assertedDate(a.embeddedPayload);
  const theirs = assertedDate(a.mirrorPayload);
  // [polish] Compare as real dates, not lexicographically: a datetime / slashed / malformed date must
  // NOT silently skip the downgrade. When both parse, use the date; otherwise fall back to the
  // unambiguous `supersedes` branch (never a false "not stale" from a string quirk).
  const od = parseDate(ours);
  const td = parseDate(theirs);
  const mirrorIsNewer = od !== null && td !== null && td > od;

  if (mirrorSupersedesUs || mirrorIsNewer) {
    const out: StaleResult = { stale: true, code: "OMW-W051" };
    if (theirs !== null) out.mirrorAssertedDate = theirs;
    return out;
  }
  return { stale: false }; // a genuine mismatch, not a supersede
}
