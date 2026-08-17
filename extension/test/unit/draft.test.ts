import { describe, expect, test } from "vitest";
import {
  newDraft,
  setField,
  setEvidence,
  omissions,
  fieldsWithoutEvidence,
} from "../../src/author/draft.js";

describe("draft model — immutable payload + per-field evidence", () => {
  test("setField writes a JSON-pointer leaf without mutating the input", () => {
    const d0 = newDraft();
    const d1 = setField(d0, "/deal/capRate", 0.0575);
    expect((d1.payload.deal as Record<string, unknown>).capRate).toBe(0.0575);
    expect(d0.payload).toEqual({}); // original untouched
  });

  test("a value with no evidence is flagged until setEvidence adds a page+quote", () => {
    let d = setField(newDraft(), "/deal/capRate", 0.0575);
    expect(fieldsWithoutEvidence(d)).toContain("/deal/capRate");
    d = setEvidence(d, "/deal/capRate", { page: 1, quote: "Cap Rate: 5.75%" });
    expect(fieldsWithoutEvidence(d)).not.toContain("/deal/capRate");
  });

  test("newDraft(seed) seeds the payload for reprice", () => {
    const d = newDraft({ deal: { noi: 100 } });
    expect((d.payload.deal as Record<string, unknown>).noi).toBe(100);
  });

  test("omissions lists schema-known paths absent from the payload", () => {
    const d = setField(newDraft(), "/deal/noi", 100);
    expect(omissions(d, ["/deal/noi", "/deal/askingPrice"])).toEqual(["/deal/askingPrice"]);
  });
});
