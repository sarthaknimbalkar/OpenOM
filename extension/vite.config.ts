import { resolve } from "node:path";
import { defineConfig } from "vite";

// Plain vite multi-entry build for MV3: the service worker and the popup are separate entry points;
// public/manifest.json is copied verbatim to dist. `openom-js` aliases the /js source so vite
// bundles the shared trust core (A) directly. node:zlib is external — read.ts uses the in-browser
// pdf.js fallback (§D.2.2), so the bundle never needs Node's zlib.
export default defineConfig({
  root: __dirname,
  publicDir: "public",
  resolve: {
    alias: { "openom-js": resolve(__dirname, "../js/src/index.ts") },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2022",
    rollupOptions: {
      input: {
        "service-worker": resolve(__dirname, "src/service-worker.ts"),
        popup: resolve(__dirname, "popup.html"),
      },
      external: ["node:zlib"],
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "[name].[ext]",
      },
    },
  },
});
