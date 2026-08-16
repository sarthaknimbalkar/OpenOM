import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      // parse.ts's raw-text scanner + read.ts's fallbacks have defensive branches only real
      // corrupt/edge PDFs hit; a slightly lower branch floor keeps the gate firm without
      // chasing unreachable bytes.
      thresholds: { lines: 85, functions: 85, branches: 80, statements: 85 },
    },
  },
});
