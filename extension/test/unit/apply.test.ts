import { describe, expect, test } from "vitest";
import { newDraft, fieldsWithoutEvidence } from "../../src/author/draft.js";
import { applyExtraction } from "../../src/author/extract/apply.js";

describe("applyExtraction — fold extraction into the draft", () => {
  test("sets fields + evidence; evidence clears the no-evidence flag", () => {
    const d = applyExtraction(newDraft(), {
      fields: [{ path: "/deal/capRate", value: 0.0575, evidence: { page: 1, quote: "Cap Rate 5.75%" } }],
    });
    expect((d.payload.deal as Record<string, unknown>).capRate).toBe(0.0575);
    expect(fieldsWithoutEvidence(d)).not.toContain("/deal/capRate");
  });

  test("a rent-schedule period keeps its extracted source tag", () => {
    const d = applyExtraction(newDraft(), {
      fields: [{ path: "/lease/rentSchedule", value: [{ annualRent: 100, source: "extracted" }] }],
    });
    expect(((d.payload.lease as Record<string, unknown[]>).rentSchedule[0] as Record<string, unknown>).source).toBe("extracted");
  });

  test("human-only + system fields from the model are DROPPED, not applied (#90)", () => {
    const d = applyExtraction(newDraft(), {
      fields: [
        { path: "/assertedBy/broker", value: "Attacker" },
        { path: "/assertedDate", value: "2000-01-01" },
        { path: "/deal/noiType", value: "in-place" },
        { path: "/meta/supersedes", value: "sha256:evil" },
        { path: "/deal/capRate", value: 0.06 }, // allowed → applied
      ],
    });
    expect(d.payload.assertedBy).toBeUndefined();
    expect(d.payload.assertedDate).toBeUndefined();
    expect(d.payload.meta).toBeUndefined();
    expect((d.payload.deal as Record<string, unknown>).noiType).toBeUndefined();
    expect((d.payload.deal as Record<string, unknown>).capRate).toBe(0.06);
  });
});
