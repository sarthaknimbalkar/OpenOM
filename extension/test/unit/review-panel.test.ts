// @vitest-environment jsdom
import { describe, expect, test } from "vitest";
import type { ValidationReport } from "openom-js";
import { newDraft, setField } from "../../src/author/draft.js";
import { renderReview, repriceDiff } from "../../src/author/review-panel.js";

const clean: ValidationReport = {
  specVersion: "0.1",
  validatorVersion: "0.1.0",
  errors: [],
  warnings: [],
  info: [],
  summary: { errorCount: 0, warningCount: 0, infoCount: 0 },
  blocked: false,
};
const withError: ValidationReport = {
  ...clean,
  errors: [{ code: "OMV-E001", severity: "error", path: "/deal/capRate", message: "must be number" }],
  summary: { errorCount: 1, warningCount: 0, infoCount: 0 },
  blocked: true,
};
const withWarning: ValidationReport = {
  ...clean,
  warnings: [{ code: "OMW-W020", severity: "warning", path: "/deal", message: "cap rate vs NOI/price off" }],
  summary: { errorCount: 0, warningCount: 1, infoCount: 0 },
};

describe("renderReview — assert gate + contract sections", () => {
  test("schema error disables Assert; a value without evidence is flagged", () => {
    const root = document.createElement("div");
    const draft = setField(newDraft(), "/deal/capRate", 0.0575);
    renderReview(root, draft, { report: withError, diff: null });
    const assert = root.querySelector("#assert") as HTMLButtonElement;
    expect(assert.disabled).toBe(true);
    expect(root.querySelectorAll(".review-field").length).toBeGreaterThan(0);
    expect(root.querySelectorAll(".field-flag").length).toBeGreaterThan(0);
  });

  test("error-free draft enables Assert; residual warnings are shown", () => {
    const root = document.createElement("div");
    const draft = setField(newDraft(), "/deal/capRate", 0.0575);
    renderReview(root, draft, { report: withWarning, diff: null });
    expect((root.querySelector("#assert") as HTMLButtonElement).disabled).toBe(false);
    const w = root.querySelector(".residual-warning");
    expect(w?.textContent).toContain("OMW-W020");
  });

  test("Assert is never enabled by anything but a zero error count", () => {
    const root = document.createElement("div");
    renderReview(root, newDraft(), { report: withError, diff: null });
    expect((root.querySelector("#assert") as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("repriceDiff", () => {
  test("reports changed leaves and carries supersedes = prior hash", () => {
    const diff = repriceDiff({ deal: { noi: 100 } }, { deal: { noi: 120 } }, "sha256:prior");
    expect(diff.changed).toContainEqual(["/deal/noi", 100, 120]);
    expect(diff.supersedes).toBe("sha256:prior");
  });

  test("reports added and removed leaves", () => {
    const diff = repriceDiff({ deal: { noi: 100 } }, { deal: { askingPrice: 9 } }, "sha256:p");
    expect(diff.removed).toContain("/deal/noi");
    expect(diff.added).toContain("/deal/askingPrice");
  });
});
