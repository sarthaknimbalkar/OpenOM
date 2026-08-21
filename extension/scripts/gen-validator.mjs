// Generate an eval-free standalone JSON Schema validator for the MV3 consumer bundle.
//
// MV3's content-security policy forbids `unsafe-eval`, so ajv's runtime `new Function` compile
// cannot run in the service worker ([OM-DoD-006]). This precompiles spec/om-0.1.schema.json to
// plain CommonJS at build time (ajv standalone codegen); vite inlines it plus its format tables and
// runtime helpers - all ordinary JS, zero eval. The options MUST match js/src/validate.ts compile()
// so client-side schema validation is bit-for-bit the same as the deterministic core ([OM-VAL-002]).
//
// Output is a generated artifact (git-ignored, regenerated every build), consumed via src/validator.ts.
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import standaloneCode from "ajv/dist/standalone/index.js";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const schemaPath = resolve(root, "../../spec/om-0.1.schema.json");
const outDir = resolve(root, "../src/generated");
const outPath = resolve(outDir, "validator.cjs");

const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
const Ctor = Ajv2020.default ?? Ajv2020;
const ajv = new Ctor({ allErrors: true, strict: false, code: { source: true } });
(addFormats.default ?? addFormats)(ajv, { mode: "full" });
const validate = ajv.compile(schema);
const code = (standaloneCode.default ?? standaloneCode)(ajv, validate);

mkdirSync(outDir, { recursive: true });
writeFileSync(outPath, code);
console.log(`gen-validator: wrote ${outPath} (${code.length} bytes, eval-free)`);
