// The assertion step: turn a reviewed Draft into the payload the broker is asserting, then validate
// and embed. `finalize` is pure (the clock is passed in as `today` — the deterministic core never
// reads a clock); `assertAndEmbed` refuses to embed a schema-invalid payload; `handBack` hands the
// produced OM to the broker as a download. Zero inference. Called only after an explicit human Assert.
import type { Draft } from "./draft.js";
import type { BrokerProfile } from "./profile.js";
import type { ValidationReport } from "openom-js";

/** Spec constants stamped at assertion — boilerplate, not broker-entered facts (§E). */
const CONTEXT = ["https://schema.org", "https://verveliolabs.com/openom/ns/0.1"];

/**
 * Produce the payload the broker asserts: stamp the spec constants, `assertedBy` from the profile,
 * `assertedDate = today`; promote every rentSchedule `source` "extracted"→"asserted"; and on a
 * reprice set `meta.supersedes` to the prior payload's hash. The panel validates THIS shape (not the
 * raw draft) so the Assert gate reflects what would actually be embedded.
 */
export function finalize(
  draft: Draft,
  profile: BrokerProfile,
  today: string,
  prior: { payloadHash: string } | null,
  sourceDocHash?: string,
): Record<string, unknown> {
  const p = structuredClone(draft.payload);
  p["@context"] = CONTEXT;
  p["@type"] = "RealEstateListing";
  p["specVersion"] = "0.1";
  p["assertedBy"] = { broker: profile.broker, brokerage: profile.brokerage, license: profile.license };
  p["assertedDate"] = today;

  const meta = (typeof p.meta === "object" && p.meta !== null ? p.meta : {}) as Record<string, unknown>;
  meta.supersedes = prior ? prior.payloadHash : (meta.supersedes ?? null);
  // Provenance: record the hash of the source document this payload was asserted against ([#96]).
  if (sourceDocHash) meta.sourceDocHash = sourceDocHash;
  p["meta"] = meta;

  const lease = p.lease as { rentSchedule?: Record<string, unknown>[] } | undefined;
  if (lease?.rentSchedule) {
    lease.rentSchedule = lease.rentSchedule.map((r) => ({
      ...r,
      source: r.source === "extracted" ? "asserted" : r.source,
    }));
  }
  return p;
}

/** Re-validate the final payload (must be error-free) then embed. Never embeds a schema-invalid OM. */
export async function assertAndEmbed(
  finalPayload: Record<string, unknown>,
  bytes: Uint8Array,
  validate: (p: Record<string, unknown>) => ValidationReport,
  embed: (b: Uint8Array, p: Record<string, unknown>) => Promise<Uint8Array>,
): Promise<Uint8Array> {
  const report = validate(finalPayload);
  if (report.errors.length > 0) {
    throw new Error(`cannot embed: ${report.errors.length} schema error(s): ${report.errors.map((e) => e.code).join(", ")}`);
  }
  return embed(bytes, finalPayload);
}

/**
 * A meaningful download name from the payload's street address (or the source URL's basename), always
 * ending `-openom.pdf`; falls back to `openom-embedded.pdf` ([#99]). Sanitized to a safe filename.
 */
export function suggestedFilename(payload: Record<string, unknown>, sourceUrl?: string): string {
  const addr = (payload.property as Record<string, unknown> | undefined)?.address as
    | Record<string, unknown>
    | undefined;
  const street = typeof addr?.streetAddress === "string" ? addr.streetAddress : "";
  let base = street;
  if (!base && sourceUrl) {
    try {
      base = new URL(sourceUrl).pathname.split("/").pop()?.replace(/\.pdf$/i, "") ?? "";
    } catch {
      base = "";
    }
  }
  const slug = base
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return slug ? `${slug}-openom.pdf` : "openom-embedded.pdf";
}

/** Hand the embedded OM to the broker as a download (panel document; no `downloads` permission). */
export function handBack(out: Uint8Array, filename: string): void {
  const url = URL.createObjectURL(new Blob([new Uint8Array(out)], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
