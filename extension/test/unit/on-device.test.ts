import { afterEach, describe, expect, test, vi } from "vitest";
import { onDeviceExtractor } from "../../src/author/extract/on-device.js";

const g = globalThis as Record<string, unknown>;

function installFakeModel(reply: unknown): void {
  g.LanguageModel = {
    create: async () => ({ prompt: async () => JSON.stringify(reply) }),
  };
}

afterEach(() => {
  delete g.LanguageModel;
  vi.restoreAllMocks();
});

describe("onDeviceExtractor — Prompt API adapter", () => {
  test("available() reflects the Prompt API global", async () => {
    expect(await onDeviceExtractor.available()).toBe(false);
    installFakeModel({ fields: [] });
    expect(await onDeviceExtractor.available()).toBe(true);
  });

  test("extract parses the model JSON and NEVER calls fetch", async () => {
    installFakeModel({
      fields: [{ path: "/deal/capRate", value: 0.0575, evidence: { page: 1, quote: "Cap Rate: 5.75%" } }],
    });
    const fetchSpy = vi.fn();
    g.fetch = fetchSpy;
    const r = await onDeviceExtractor.extract([{ page: 1, text: "Cap Rate: 5.75%" }]);
    expect(r.fields[0]?.path).toBe("/deal/capRate");
    expect(r.fields[0]?.evidence?.page).toBe(1);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  test("malformed model output throws a clear error", async () => {
    g.LanguageModel = { create: async () => ({ prompt: async () => "not json" }) };
    await expect(onDeviceExtractor.extract([{ page: 1, text: "x" }])).rejects.toThrow();
  });
});
