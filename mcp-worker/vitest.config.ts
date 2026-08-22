import { defineConfig } from "vitest/config";

// Unit tests for the public MCP Worker's deterministic helpers (fetchPdf redirect/SSRF, safeUrl).
// Node env; JSON imports + openom-js resolve through Vite/esbuild exactly as the Worker bundle does.
export default defineConfig({
  test: { include: ["test/**/*.test.ts"], environment: "node" },
});
