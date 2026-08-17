import { resolve } from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "openom-js/webhook": resolve(__dirname, "../js/src/webhook.ts"),
      "openom-js": resolve(__dirname, "../js/src/index.ts"),
    },
  },
  test: { environment: "node", include: ["test/unit/**/*.test.ts"] },
});
