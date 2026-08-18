// MV3 build: each entry is its own single-input vite build. The service worker + the classic content
// script are SELF-CONTAINED (inlineDynamicImports) because neither can load an ES-module chunk. The
// sidepanel is a full extension PAGE, so it CAN — under the default CSP (script-src 'self') a
// same-origin chunk loads — and it opts into chunking (`chunks: true`). public/ is copied once.
//
// Bundle sizes (#150 / #165): sidepanel.js is now ~788 KB (pd-lib + ajv-standalone + the schema form),
// with pdf.js split into a ~378 KB on-demand chunk (sidepanel-<hash>.js) loaded only when text
// extraction / encrypted-decrypt actually runs. service-worker.js ~896 KB (#103), popup 16 KB (#102),
// options 4 KB, link-badger 2 KB, pdf.worker.mjs 2.35 MB (separate on-demand file). pd-lib/ajv/@noble
// are duplicated across the SW and sidepanel because MV3 gives them separate execution contexts with
// no shared chunk. The lazy split (`base: "./"` for relative chunk URLs) is proven by the headed gate
// (20/20 — the encrypted-decrypt + on-device-extraction specs load the chunk).
import { copyFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import "./scripts/gen-validator.mjs"; // regenerate the eval-free schema validator before bundling

const root = dirname(fileURLToPath(import.meta.url));
// Narrow sub-entry so the popup (webhook/publish only) doesn't drag the whole barrel — and with it
// pd-lib + ajv-formats — into its bundle ([#102]). More-specific key first.
const alias = {
  "openom-js/webhook": resolve(root, "../js/src/webhook.ts"),
  "openom-js": resolve(root, "../js/src/index.ts"),
};

// `format` is "es" for the service worker + extension pages, but "iife" for the declarative content
// script — MV3 content_scripts run as CLASSIC scripts, not ES modules ([#69]).
// `chunks: true` lets dynamic import()s split into on-demand chunks instead of being inlined. Only
// safe for a full extension PAGE (module <script>), which can load a same-origin chunk under the MV3
// default CSP (script-src 'self'); the service worker + classic content script CANNOT, so they stay
// inlined. `base: "./"` keeps the emitted import paths relative so they resolve under chrome-extension://.
async function one(input, name, first, format = "es", chunks = false) {
  await build({
    root,
    base: "./",
    configFile: false,
    publicDir: first ? "public" : false,
    resolve: { alias },
    logLevel: "warn",
    build: {
      outDir: "dist",
      emptyOutDir: first,
      target: "es2022",
      rollupOptions: {
        input,
        external: ["node:zlib"],
        output: {
          entryFileNames: `${name}.js`,
          chunkFileNames: `${name}-[hash].js`,
          format,
          inlineDynamicImports: !chunks,
        },
      },
    },
  });
}

await one(resolve(root, "src/service-worker.ts"), "service-worker", true);
await one(resolve(root, "src/popup/popup.ts"), "popup", false);
await one(resolve(root, "src/author/panel.ts"), "sidepanel", false, "es", true); // pdf.js → lazy chunk (#165)
await one(resolve(root, "src/options.ts"), "options", false);
await one(
  resolve(root, "src/content/link-badger.ts"),
  "link-badger",
  false,
  "iife",
); // classic script

// The author panel extracts OM text with pdf.js, which needs its worker as a web-accessible resource
// (the panel is a full page and CAN spawn the Worker the consumer service worker could not).
copyFileSync(
  resolve(root, "../js/node_modules/pdfjs-dist/legacy/build/pdf.worker.mjs"),
  resolve(root, "dist/pdf.worker.mjs"),
);
console.log(
  "built dist (service-worker + popup + sidepanel[+pdf.js lazy chunk] + options + pdf.worker)",
);
