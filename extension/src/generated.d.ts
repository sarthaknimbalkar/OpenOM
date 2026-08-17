// The generated standalone validator (scripts/gen-validator.mjs output) is untyped CommonJS. Give
// any `.cjs` import the openOM validator signature — the sole `.cjs` import in this package is that
// validator. Eval-free by construction; vite bundles it for the CSP-locked MV3 consumer.
declare module "*.cjs" {
  import type { PrecompiledValidate } from "openom-js";
  const validate: PrecompiledValidate;
  export default validate;
}
