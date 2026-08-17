// MV3 build: each entry is a SELF-CONTAINED bundle (inlineDynamicImports), because a service worker
// and extension pages cannot load vite's code-split dynamic chunks. Two single-input vite builds →
// dist/service-worker.js + dist/popup.js; public/ (manifest, popup.html, popup.css) is copied once.
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
console.log("built dist (service-worker + popup + sidepanel, dynamic imports inlined)");
