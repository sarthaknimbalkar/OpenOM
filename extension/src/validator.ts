// Typed handle to the generated eval-free schema validator (scripts/gen-validator.mjs). The .cjs it
// wraps is a build artifact (git-ignored, regenerated every build); generated.d.ts types the import.
// This exists so the CSP-locked MV3 consumer validates payloads with the SAME schema as /core, but
// without ajv's runtime `new Function` - which the service-worker CSP forbids ([OM-DoD-006]).
import validate from "./generated/validator.cjs";
import type { PrecompiledValidate } from "openom-js";

export const precompiledValidate: PrecompiledValidate = validate;
