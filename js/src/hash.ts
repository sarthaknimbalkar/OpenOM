import { canonicalize } from "./canonicalize.js";
import { sha256Hex } from "./crypto.js";

/**
 * Compute the OpenOM integrity hash of a payload.
 *
 * Spec: §C.3 [OM-CANON-016]. The preimage is the payload with `meta.signature`
 * REMOVED (absent, not null) so a signature can be added later without
 * disturbing the hash ([OM-CANON-017]). Every other field — including
 * `meta.sourceDocHash` and `meta.supersedes` — is part of the preimage.
 *
 * @returns `"sha256:" + lowercase_hex(SHA-256(JCS(preimage)))` ([OM-CANON-003]).
 */
export function payloadHash(payload: unknown): string {
  const preimage = stripSignature(payload);
  return `sha256:${sha256Hex(canonicalize(preimage))}`;
}

/**
 * Return a shallow-cloned payload with `meta.signature` removed if present.
 * Only `meta.signature` is excluded from the preimage — no other field
 * ([OM-CANON-017]).
 */
function stripSignature(payload: unknown): unknown {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return payload;
  }
  const obj = payload as Record<string, unknown>;
  const meta = obj["meta"];
  if (meta === null || typeof meta !== "object" || Array.isArray(meta)) {
    return payload;
  }
  const metaObj = meta as Record<string, unknown>;
  if (!("signature" in metaObj)) {
    return payload;
  }
  const { signature: _signature, ...metaWithoutSignature } = metaObj;
  return { ...obj, meta: metaWithoutSignature };
}
