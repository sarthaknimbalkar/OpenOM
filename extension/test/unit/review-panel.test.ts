// @vitest-environment jsdom
import { describe, expect, test } from "vitest";
import type { ValidationReport } from "openom-js";
import { newDraft } from "../../src/author/draft.js";
import { renderDerived, repriceDiff } from "../../src/author/review-panel.js";

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

describe("renderDerived - assert gate + finalized preview", () => {
  test("schema error disables Assert; finalized preview shows the stamped fields (#95)", () => {
    const c = document.createElement("div");
    renderDerived(c, newDraft({}), {
      report: withError,
      diff: null,
      finalized: { assertedBy: { broker: "Jane Broker" }, assertedDate: "2026-08-18" },
    });
    expect((c.querySelector("#assert") as HTMLButtonElement).disabled).toBe(true);
    const preview = c.querySelector(".finalized-preview")?.textContent ?? "";
    expect(preview).toContain("Jane Broker");
    expect(preview).toContain("2026-08-18");
  });

  test("error-free draft enables Assert; residual warnings shown", () => {
    const c = document.createElement("div");
    renderDerived(c, newDraft({}), { report: withWarning, diff: null, finalized: {} });
    expect((c.querySelector("#assert") as HTMLButtonElement).disabled).toBe(false);
    expect(c.querySelector(".residual-warning")?.textContent).toContain("OMW-W020");
  });

  test("Assert never enabled by anything but a zero error count", () => {
    const c = document.createElement("div");
    renderDerived(c, newDraft({}), { report: withError, diff: null, finalized: {} });
    expect((c.querySelector("#assert") as HTMLButtonElement).disabled).toBe(true);
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
