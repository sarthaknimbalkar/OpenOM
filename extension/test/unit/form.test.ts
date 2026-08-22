// @vitest-environment jsdom
import { describe, expect, test, vi } from "vitest";
import { newDraft } from "../../src/author/draft.js";
import { buildForm, type FormCallbacks } from "../../src/author/form.js";

const cbs = (): FormCallbacks => ({
  onField: vi.fn(),
  onEvidence: vi.fn(),
  onAddRentPeriod: vi.fn(),
  onRemoveRentPeriod: vi.fn(),
  onViewPage: vi.fn(),
});

describe("buildForm (#77/#93)", () => {
  test("typed controls edit the draft via onField", () => {
    const root = document.createElement("div");
    const cb = cbs();
    buildForm(root, newDraft({ deal: { noi: 100 } }), cb);
    const cap = root.querySelector('[data-path="/deal/capRate"]') as HTMLInputElement;
    expect(cap.type).toBe("number");
    cap.value = "0.06";
    cap.dispatchEvent(new Event("input"));
    expect(cb.onField).toHaveBeenCalledWith("/deal/capRate", 0.06);
  });

  test("#93 noiType/noiAsOfDate controls appear only when deal.noi is set", () => {
    const withNoi = document.createElement("div");
    buildForm(withNoi, newDraft({ deal: { noi: 100 } }), cbs());
    expect(withNoi.querySelector('select[data-path="/deal/noiType"]')).not.toBeNull();
    expect(withNoi.querySelector('[data-path="/deal/noiAsOfDate"]')).not.toBeNull();

    const noNoi = document.createElement("div");
    buildForm(noNoi, newDraft({}), cbs());
    expect(noNoi.querySelector('[data-path="/deal/noiType"]')).toBeNull();
  });

  test("per-field evidence inputs call onEvidence", () => {
    const root = document.createElement("div");
    const cb = cbs();
    buildForm(root, newDraft({}), cb);
    const row = root.querySelector('[data-path="/deal/capRate"]')!.closest(".review-field")!;
    const q = row.querySelector("input.ev-quote") as HTMLInputElement;
    q.value = "Cap Rate 6%";
    q.dispatchEvent(new Event("input"));
    expect(cb.onEvidence).toHaveBeenCalledWith("/deal/capRate", { page: undefined, quote: "Cap Rate 6%" });
  });

  test("[M7] a cited field offers a 'view page' jump to the source OM page", () => {
    const root = document.createElement("div");
    const cb = cbs();
    // A draft whose capRate carries page evidence.
    let d = newDraft({ deal: { capRate: 0.06 } });
    d = { ...d, evidence: { "/deal/capRate": { page: 3, quote: "Cap Rate 6%" } } };
    buildForm(root, d, cb);
    const row = root.querySelector('[data-path="/deal/capRate"]')!.closest(".review-field")!;
    (row.querySelector("button.ev-view") as HTMLButtonElement).click();
    expect(cb.onViewPage).toHaveBeenCalledWith(3);
  });

  test("rent-schedule editor fires add/remove callbacks; advanced raw JSON present", () => {
    const root = document.createElement("div");
    const cb = cbs();
    buildForm(root, newDraft({ lease: { rentSchedule: [{ annualRent: 100, source: "extracted" }] } }), cb);
    (root.querySelector(".add-rent") as HTMLButtonElement).click();
    expect(cb.onAddRentPeriod).toHaveBeenCalled();
    (root.querySelector(".rent-row .rm-rent") as HTMLButtonElement).click();
    expect(cb.onRemoveRentPeriod).toHaveBeenCalledWith(0);
    expect(root.querySelector("textarea.draft-json")).not.toBeNull();
  });
});
