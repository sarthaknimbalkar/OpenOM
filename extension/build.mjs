// MV3 build: each entry is a SELF-CONTAINED bundle (inlineDynamicImports), because a service worker
// and extension pages cannot load vite's code-split dynamic chunks. Two single-input vite builds →
// dist/service-worker.js + dist/popup.js; public/ (manifest, popup.html, popup.css) is copied once.
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
async function one(input, name, first, format = "es") {
  await build({
    root,
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
        output: { entryFileNames: `${name}.js`, format, inlineDynamicImports: true },
      },
    },
  });
}

await one(resolve(root, "src/service-worker.ts"), "service-worker", true);
await one(resolve(root, "src/popup/popup.ts"), "popup", false);
await one(resolve(root, "src/author/panel.ts"), "sidepanel", false);
await one(resolve(root, "src/options.ts"), "options", false);
await one(resolve(root, "src/content/link-badger.ts"), "link-badger", false, "iife"); // classic script

// The author panel extracts OM text with pdf.js, which needs its worker as a web-accessible resource
// (the panel is a full page and CAN spawn the Worker the consumer service worker could not).
copyFileSync(
  resolve(root, "../js/node_modules/pdfjs-dist/legacy/build/pdf.worker.mjs"),
  resolve(root, "dist/pdf.worker.mjs"),
);
console.log("built dist (service-worker + popup + sidepanel + pdf.worker, dynamic imports inlined)");
