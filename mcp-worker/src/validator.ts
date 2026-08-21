// Typed handle to the generated eval-free schema validator (scripts/gen-validator.mjs → CommonJS).
// Passed to validatePayload so the Worker never triggers ajv's runtime (eval) compile.
import type { PrecompiledValidate } from "openom-js";
// @ts-expect-error - generated untyped CommonJS
import validate from "./generated/validator.cjs";

export const precompiledValidate: PrecompiledValidate = validate as PrecompiledValidate;
