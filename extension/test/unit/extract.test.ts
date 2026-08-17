import { describe, expect, test } from "vitest";
import { hostedStub } from "../../src/author/extract/hosted-stub.js";
import { makeTestDouble } from "../../src/author/extract/test-double.js";
import { pickExtractor } from "../../src/author/extract/pick.js";
import type { ExtractionResult } from "../../src/author/extract/types.js";

const R: ExtractionResult = { fields: [{ path: "/deal/noi", value: 100 }] };

describe("extractor seam", () => {
  test("hosted-stub is a disabled, throwing seam (never a live call)", async () => {
    expect(await hostedStub.available()).toBe(false);
    await expect(hostedStub.extract([])).rejects.toThrow(/separate Vervelio service/);
  });

  test("test-double is deterministic and available", async () => {
    const ex = makeTestDouble(R);
    expect(await ex.available()).toBe(true);
    expect(await ex.extract([])).toEqual(R);
  });

  test("pickExtractor selects the first available, else null", async () => {
    expect(await pickExtractor([hostedStub])).toBeNull();
    const td = makeTestDouble(R);
    expect(await pickExtractor([hostedStub, td])).toBe(td);
    expect(await pickExtractor([])).toBeNull();
  });
});
