// MV3 build: each entry is a SELF-CONTAINED bundle (inlineDynamicImports), because a service worker
// and extension pages cannot load vite's code-split dynamic chunks. Two single-input vite builds →
// dist/service-worker.js + dist/popup.js; public/ (manifest, popup.html, popup.css) is copied once.
import { copyFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import "./scripts/gen-validator.mjs"; // regenerate the eval-free schema validator before bundling

const root = dirname(fileURLToPath(import.meta.url));
const alias = { "openom-js": resolve(root, "../js/src/index.ts") };

async function one(input, name, first) {
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
        output: { entryFileNames: `${name}.js`, format: "es", inlineDynamicImports: true },
      },
    },
  });
}

await one(resolve(root, "src/service-worker.ts"), "service-worker", true);
await one(resolve(root, "src/popup/popup.ts"), "popup", false);
await one(resolve(root, "src/author/panel.ts"), "sidepanel", false);

// The author panel extracts OM text with pdf.js, which needs its worker as a web-accessible resource
// (the panel is a full page and CAN spawn the Worker the consumer service worker could not).
copyFileSync(
  resolve(root, "../js/node_modules/pdfjs-dist/legacy/build/pdf.worker.mjs"),
  resolve(root, "dist/pdf.worker.mjs"),
);
console.log("built dist (service-worker + popup + sidepanel + pdf.worker, dynamic imports inlined)");
