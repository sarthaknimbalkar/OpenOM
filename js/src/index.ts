/**
 * openOM `/js` — TypeScript reference implementation.
 *
 * Deterministic; zero inference (consumer-mode + shared engine). Public API for
 * canonicalization, integrity hashing, verification, hardened parsing, embed/read
 * (§D — read via pdf.js, write via pdf-lib), schema validation (§H, ajv), and the
 * re-embed provenance warning.
 */
export { canonicalize } from "./canonicalize.js";
export { payloadHash, preimageBytes } from "./hash.js";
export { embedPayload } from "./embed.js";
export { reembedWarnings } from "./reembed.js";
export { integrityHashOfBytes, verifyIntegrity, type IntegrityResult } from "./verify.js";
export { parsePayload, DEFAULT_MAX_PAYLOAD_BYTES, type ParseOptions } from "./parse.js";
export { sha256Hex } from "./crypto.js";
export {
  readPayloadFromBytes,
  type ReadResult,
  type ReadState,
  type ReadVerification,
} from "./read.js";
export { validatePayload, type Finding, type ValidationReport } from "./validate.js";
export { OmIoError, type OmIoCode } from "./errors.js";
