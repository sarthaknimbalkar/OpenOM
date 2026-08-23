// @vitest-environment jsdom
import { describe, expect, test } from "vitest";
import type { ValidationReport } from "openom-js";
import { newDraft } from "../../src/author/draft.js";
import { plainMessage, renderDerived, repriceDiff } from "../../src/author/review-panel.js";

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

  test("[M7] errors + reprice diff read in human language, not JSON pointers or a raw hash", () => {
    const c = document.createElement("div");
    renderDerived(c, newDraft({}), {
      report: withError,
      diff: {
        added: [],
        changed: [["/deal/askingPrice", 1_000_000, 1_200_000]],
        removed: [],
        supersedes: "sha256:" + "a".repeat(58),
      },
      finalized: {},
    });
    const err = c.querySelector(".schema-error")?.textContent ?? "";
    expect(err).toContain("0.0625"); // plain-English cap-rate instruction, not a raw pointer
    expect(err).not.toContain("/deal/capRate");
    const changed = c.querySelector(".diff-changed")?.textContent ?? "";
    expect(changed).toContain("Deal › Asking Price");
    const sup = c.querySelector(".diff-supersedes")?.textContent ?? "";
    expect(sup).toContain("replaces your prior assertion");
    expect(sup).not.toContain("a".repeat(58)); // not the full 64-char hash
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

describe("plain-English coaching (non-technical broker validation errors)", () => {
  test("cap-rate error renders as a decimal-fraction instruction, not the raw schema string", () => {
    const c = document.createElement("div");
    renderDerived(c, newDraft({}), { report: withError, diff: null, finalized: {} });
    const err = c.querySelector(".schema-error")?.textContent ?? "";
    expect(err).toContain("0.0625");
    expect(err).not.toContain("must be number");
  });

  test("warnings section explains that warnings never block", () => {
    const c = document.createElement("div");
    renderDerived(c, newDraft({}), { report: withWarning, diff: null, finalized: {} });
    expect(c.querySelector(".warnings-note")?.textContent).toContain("don't block");
  });
});

describe("plainMessage", () => {
  test("known broker codes are plain; unknown falls back to path + code", () => {
    expect(plainMessage("OMV-E002", "/deal/noiType", "x")).toContain("in-place or pro-forma");
    expect(plainMessage("OMV-E001", "/currency", "x")).toContain("USD");
    const f = plainMessage("OMV-E001", "/property/buildingSF", "must be a number");
    expect(f).toContain("(OMV-E001)");
  });
});
