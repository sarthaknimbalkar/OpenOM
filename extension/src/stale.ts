// Stale-vs-tamper (§AA [OM-TRUST-009], OMW-W051). When the embedded payload's hash differs from the
// origin mirror's CURRENT hash, decide whether the mirror is a genuine *newer* assertion (stale/
// superseded — surface a warning, keep the badge) or an actual mismatch (leave it to the badge).

export interface StaleResult {
  stale: boolean;
  code?: "OMW-W051";
  mirrorAssertedDate?: string;
}

function assertedDate(p: Record<string, unknown> | null): string | null {
  const d = p?.["assertedDate"];
  return typeof d === "string" ? d : null;
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
  const mirrorIsNewer = ours !== null && theirs !== null && theirs > ours;

  if (mirrorSupersedesUs || mirrorIsNewer) {
    return { stale: true, code: "OMW-W051", mirrorAssertedDate: theirs ?? undefined };
  }
  return { stale: false }; // a genuine mismatch, not a supersede
}
