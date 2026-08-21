// Build the embeddable badge (#144) into a single self-contained classic script a portal can drop in
// with one <script> tag: widget/dist/openom-badge.js. IIFE (not ESM) so it works via a plain script
// tag on any page; minified; the openom-js read/verify path (pd-lib + @noble + tldts) is inlined.
// Deterministic + inference-free - verified by assert-no-inference over the emitted bundle.
import { build } from "esbuild";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

await build({
  entryPoints: [resolve(here, "openom-badge.ts")],
  outfile: resolve(here, "dist/openom-badge.js"),
  bundle: true,
  format: "iife",
  target: "es2020",
  platform: "browser",
  minify: true,
  sourcemap: true,
  legalComments: "none",
  logLevel: "info",
});

console.log("wrote widget/dist/openom-badge.js");
