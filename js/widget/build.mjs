// Build the embeddable badge (#144) into a single self-contained classic script a portal can drop in
// with one <script> tag: widget/dist/openom-badge.js. IIFE (not ESM) so it works via a plain script
// tag on any page; minified; the openom-js read/verify path (pd-lib + @noble + tldts) is inlined.
// Deterministic + inference-free - verified by assert-no-inference over the emitted bundle.
import { build } from "esbuild";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

// Two self-contained IIFE bundles, both deterministic + inference-free (assert-no-inference gates
// widget/dist): openom-badge.js (read/verify - the badge + /verify tool) and openom-author.js (the
// hosted client-side authoring companion - embed/validate - the zero-install broker embed path #B1).
const ENTRIES = ["openom-badge.ts", "openom-author.ts"];

for (const entry of ENTRIES) {
  const out = entry.replace(/\.ts$/, ".js");
  await build({
    entryPoints: [resolve(here, entry)],
    outfile: resolve(here, "dist", out),
    bundle: true,
    format: "iife",
    target: "es2020",
    platform: "browser",
    minify: true,
    sourcemap: true,
    legalComments: "none",
    loader: { ".json": "json" },
    logLevel: "info",
  });
  console.log(`wrote widget/dist/${out}`);
}
