import { describe, expect, test } from "vitest";
import {
  newDraft,
  setField,
  setEvidence,
  omissions,
  fieldsWithoutEvidence,
  appendArrayItem,
  removeArrayItem,
} from "../../src/author/draft.js";

describe("draft model - immutable payload + per-field evidence", () => {
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

  test("[P2] flags material figures for citation, not objective fields (address/enums/dates)", () => {
    let d = setField(newDraft(), "/deal/capRate", 0.06); // material → flagged
    d = setField(d, "/property/address/streetAddress", "1 Main St"); // objective → not flagged
    d = setField(d, "/lease/leaseTypeAsserted", "NNN"); // enum → not flagged
    d = setField(d, "/lease/commencement", "2020-01-01"); // date → not flagged
    const flagged = fieldsWithoutEvidence(d);
    expect(flagged).toContain("/deal/capRate");
    expect(flagged).not.toContain("/property/address/streetAddress");
    expect(flagged).not.toContain("/lease/leaseTypeAsserted");
    expect(flagged).not.toContain("/lease/commencement");
  });

  test("[M7] does NOT flag rentSchedule/options rows or assertedBy for missing evidence", () => {
    let d = setField(newDraft(), "/lease/rentSchedule/0/annualRent", 100);
    d = setField(d, "/lease/options/0/type", "renewal");
    d = setField(d, "/assertedBy/broker", "Jane");
    const flagged = fieldsWithoutEvidence(d);
    expect(flagged.some((p) => p.startsWith("/lease/rentSchedule"))).toBe(false);
    expect(flagged.some((p) => p.startsWith("/lease/options"))).toBe(false);
    expect(flagged.some((p) => p.startsWith("/assertedBy"))).toBe(false);
  });

  test("newDraft(seed) seeds the payload for reprice", () => {
    const d = newDraft({ deal: { noi: 100 } });
    expect((d.payload.deal as Record<string, unknown>).noi).toBe(100);
  });

  test("omissions lists schema-known paths absent from the payload", () => {
    const d = setField(newDraft(), "/deal/noi", 100);
    expect(omissions(d, ["/deal/noi", "/deal/askingPrice"])).toEqual(["/deal/askingPrice"]);
  });

  test("a numeric pointer token builds an ARRAY, not an object (#86)", () => {
    const d = setField(newDraft(), "/lease/rentSchedule/0/annualRent", 100);
    const schedule = (d.payload.lease as Record<string, unknown>).rentSchedule;
    expect(Array.isArray(schedule)).toBe(true);
    expect((schedule as Record<string, unknown>[])[0]).toEqual({ annualRent: 100 });
  });

  test("appending consecutive array indices extends the array (#86)", () => {
    let d = setField(newDraft(), "/lease/rentSchedule/0/annualRent", 100);
    d = setField(d, "/lease/rentSchedule/1/annualRent", 110);
    const schedule = (d.payload.lease as Record<string, unknown>).rentSchedule as unknown[];
    expect(schedule).toHaveLength(2);
    expect(schedule[1]).toEqual({ annualRent: 110 });
  });

  test("appendArrayItem / removeArrayItem are immutable and array-safe", () => {
    const d0 = newDraft();
    let d = appendArrayItem(d0, "/lease/rentSchedule", { source: "extracted" });
    expect(Array.isArray((d.payload.lease as Record<string, unknown>).rentSchedule)).toBe(true);
    d = appendArrayItem(d, "/lease/rentSchedule", { source: "extracted" });
    expect((d.payload.lease as Record<string, unknown[]>).rentSchedule).toHaveLength(2);
    d = removeArrayItem(d, "/lease/rentSchedule", 0);
    expect((d.payload.lease as Record<string, unknown[]>).rentSchedule).toHaveLength(1);
    expect(d0.payload).toEqual({}); // original untouched
  });
});
