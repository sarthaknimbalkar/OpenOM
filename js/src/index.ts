/**
 * openOM `/js` - TypeScript reference implementation.
 *
 * Deterministic; zero inference (consumer-mode + shared engine). Public API for
 * canonicalization, integrity hashing, verification, hardened parsing, embed/read
 * (§D - read via pdf.js, write via pdf-lib), schema validation (§H, ajv), and the
 * re-embed provenance warning.
 */
export { canonicalize } from "./canonicalize.js";
export { payloadHash, preimageBytes } from "./hash.js";
export { embedPayload } from "./embed.js";
export { reembedWarnings } from "./reembed.js";
export { integrityHashOfBytes, verifyIntegrity, type IntegrityResult } from "./verify.js";
export { parsePayload, DEFAULT_MAX_PAYLOAD_BYTES, type ParseOptions } from "./parse.js";
export { sha256Hex, hmacSha256Hex, timingSafeEqualHex } from "./crypto.js";
export { verifyOrigin, canonicalMirrorUrl, type OriginResult, type MirrorFetch } from "./origin.js";
export { badgeState, honestLabel, FORBIDDEN, type BadgeState } from "./badge.js";
export {
  buildEnvelope,
  signHeaders,
  assertSafeWebhookTarget,
  assertSafeUrl,
  verifyWebhookSignature,
  type Envelope,
  type Verification,
  type VerifyResult,
} from "./webhook.js";
export {
  readPayloadFromBytes,
  type ReadResult,
  type ReadState,
  type ReadVerification,
} from "./read.js";
export {
  validatePayload,
  type Finding,
  type ValidationReport,
  type PrecompiledValidate,
} from "./validate.js";
export { consistencyFindings, DEFAULT_TOLERANCES, type Tolerances } from "./consistency.js";
export { OmIoError, type OmIoCode } from "./errors.js";
export { extractPageText, setPdfWorkerSrc, type PageText, type PageTextResult } from "./text.js";
export { pdfjsDecryptRead, type DecryptRead } from "./read-decrypt.js";
export {
  validateEnvelope,
  verifyEnvelopePayloadHash,
  ENVELOPE_SCHEMA,
  type EnvelopeValidation,
} from "./envelope.js";
export {
  validateSubscription,
  SUBSCRIPTION_SCHEMA,
  SUBSCRIPTION_EVENTS,
  type SubscriptionValidation,
} from "./subscription.js";
export { summarizeDeal, type DealSummary } from "./summary.js";
export { decryptPdf } from "./decrypt.js";
export { pdfHasSignature } from "./signature.js";
export { classifyStale, type StaleResult } from "./stale.js";
export {
  schemaFieldDescriptors,
  humanizeField,
  type FieldDescriptor,
  type FieldKind,
} from "./fields.js";
export {
  finalizePayload,
  assertAndEmbed,
  suggestedFilename,
  looksLikePdf,
  captureFromBytes,
  OM_CONTEXT,
  type AssertedByProfile,
  type Capture,
} from "./author.js";
