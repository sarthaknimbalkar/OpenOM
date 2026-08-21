/**
 * The §AA consumer trust badge — a strict precedence state machine over the four provenance layers
 * ([OM-TRUST-001/002]) plus UI-honesty copy ([OM-TRUST-003]). Deterministic; zero inference. A
 * higher state is never shown unless every lower check it depends on passed; `hash-mismatch` is
 * terminal (L3/L4 are not evaluated); `signature-verified` is unreachable in 0.1 and never returned.
 */

export type BadgeState =
  "absent" | "hash-mismatch" | "integrity-ok" | "origin-verified" | "signature-verified";

/** Words a consumer MUST NOT use for an integrity-only pass ([OM-TRUST-003]). */
export const FORBIDDEN = ["verified", "authentic", "signed", "official", "genuine"] as const;

export function badgeState(v: {
  present: boolean;
  hashValid: boolean | null;
  originVerified: boolean;
  signatureValid: boolean | null;
}): BadgeState {
  if (!v.present) return "absent";
  if (v.hashValid !== true) return "hash-mismatch"; // terminal: no L3/L4 without integrity
  if (!v.originVerified) return "integrity-ok"; // == integrity-ok / origin-unverified
  return "origin-verified"; // signature-verified unreachable in 0.1 ([OM-TRUST-002])
}

/**
 * Honest UI copy for a state. The integrity-only state MUST avoid FORBIDDEN words (it proves
 * "unaltered since embed", not authorship); origin-verified describes the domain vouch, not legal
 * identity.
 */
export function honestLabel(state: BadgeState): { label: string; caption: string } {
  switch (state) {
    case "absent":
      return { label: "No openOM data", caption: "No embedded payload found — vision fallback." };
    case "hash-mismatch":
      return {
        label: "Altered payload",
        caption: "The embedded data does not match its hash — do not trust it.",
      };
    case "integrity-ok":
      return {
        label: "Unaltered since embed",
        caption:
          "Unaltered since embed; origin not yet confirmed. The broker's opinion of value — " +
          "not proof of authorship, and not a claim the figures are true.",
      };
    case "origin-verified":
      return {
        label: "Origin-verified",
        caption:
          "This domain vouches for this exact payload (HTTPS + matching mirror) — it attests the " +
          "broker's asserted opinion, not that the figures are true.",
      };
    case "signature-verified":
      return { label: "Signature-verified", caption: "Reserved; not available in 0.1." };
  }
}
