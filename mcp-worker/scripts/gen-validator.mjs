// Generate an eval-free standalone JSON Schema validator for the Worker.
//
// Cloudflare Workers forbid `unsafe-eval`/`new Function` (like the MV3 CSP), so ajv's runtime compile
// cannot run. This precompiles spec/om-0.1.schema.json to plain CommonJS at build time (ajv standalone
// codegen); wrangler/esbuild inlines it - ordinary JS, zero eval. Options MUST match
// js/src/validate.ts + extension/scripts/gen-validator.mjs so validation is bit-for-bit identical.
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import standaloneCode from "ajv/dist/standalone/index.js";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const schema = JSON.parse(readFileSync(resolve(root, "../../spec/om-0.1.schema.json"), "utf8"));
const outDir = resolve(root, "../src/generated");
const Ctor = Ajv2020.default ?? Ajv2020;
const ajv = new Ctor({ allErrors: true, strict: false, code: { source: true } });
(addFormats.default ?? addFormats)(ajv, { mode: "full" });
const code = (standaloneCode.default ?? standaloneCode)(ajv, ajv.compile(schema));
mkdirSync(outDir, { recursive: true });
writeFileSync(resolve(outDir, "validator.cjs"), code);
console.log(`gen-validator: wrote ${code.length} bytes (eval-free)`);
