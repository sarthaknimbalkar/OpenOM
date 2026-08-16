import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { consistencyFindings } from "../src/consistency.js";

/**
 * Consistency (warning) + info tier — behavioral parity with the Python core's test_validate.
 * Internal-consistency only; warnings/info never block.
 */
const specDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec");
const stnl = () =>
  JSON.parse(readFileSync(join(specDir, "samples", "valid-stnl.json"), "utf8")) as Record<
    string,
    unknown
  >;
const codes = (p: Record<string, unknown>): string[] =>
  consistencyFindings(p).warnings.map((w) => w.code);
const deal = (p: Record<string, unknown>) => p.deal as Record<string, unknown>;
const period = (p: Record<string, unknown>, i: number) =>
  rentSchedule(p)[i] as Record<string, unknown>;
const rentSchedule = (p: Record<string, unknown>) =>
  (p.lease as Record<string, unknown>).rentSchedule as Record<string, unknown>[];

describe("consistency tier", () => {
  test("the valid sample is internally consistent (no warnings/info)", () => {
    const r = consistencyFindings(stnl());
    expect(r.warnings).toEqual([]);
    expect(r.info).toEqual([]);
  });

  test("OMW-W010 cap rate vs NOI/price", () => {
    const p = stnl();
    deal(p).capRate = 0.09;
    expect(codes(p)).toContain("OMW-W010");
  });

  test("OMW-W011 price/SF vs askingPrice/buildingSF", () => {
    const p = stnl();
    deal(p).pricePerSF = 999;
    expect(codes(p)).toContain("OMW-W011");
  });

  test("OMW-W020 year-1 rent vs in-place NOI", () => {
    const p = stnl();
    period(p, 0).annualRent = 90000;
    expect(codes(p)).toContain("OMW-W020");
  });

  test("OMW-W021 gap / OMW-W022 overlap", () => {
    const gap = stnl();
    period(gap, 1).periodStart = "2030-01-01";
    expect(codes(gap)).toContain("OMW-W021");
    const overlap = stnl();
    period(overlap, 1).periodStart = "2028-01-01";
    expect(codes(overlap)).toContain("OMW-W022");
  });

  test("OMW-W023 escalation vs step", () => {
    const p = stnl();
    period(p, 1).escalationFromPrior = 0.25;
    expect(codes(p)).toContain("OMW-W023");
  });

  test("OMW-W025 monthlyRent vs annual/12", () => {
    const p = stnl();
    period(p, 0).monthlyRent = 5000;
    expect(codes(p)).toContain("OMW-W025");
  });

  test("OMW-W026 period outside the lease term", () => {
    const p = stnl();
    period(p, 0).periodStart = "2010-01-01";
    expect(codes(p)).toContain("OMW-W026");
  });

  test("OMW-W040 net lease but landlord bears pass-throughs", () => {
    const p = stnl();
    (p.lease as Record<string, unknown>).landlordResponsibilities = { taxes: true };
    expect(codes(p)).toContain("OMW-W040");
  });

  test("OMW-W014 non-positive rent without abatement", () => {
    const p = stnl();
    period(p, 0).annualRent = 0;
    expect(codes(p)).toContain("OMW-W014");
  });

  test("OMI-I001 pro-forma NOI is info (never blocks)", () => {
    const p = stnl();
    deal(p).noiType = "pro-forma";
    const r = consistencyFindings(p);
    expect(r.info.map((i) => i.code)).toContain("OMI-I001");
  });
});
