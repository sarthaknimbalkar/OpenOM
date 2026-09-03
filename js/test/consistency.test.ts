import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { consistencyFindings, round } from "../src/consistency.js";

/**
 * Consistency (warning) + info tier - behavioral parity with the Python core's test_validate.
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
  test("currency absent on a non-US property → OMW-W061 (#119); US base stays warning-free", () => {
    const nonUs = stnl();
    (
      (nonUs.property as Record<string, unknown>).address as Record<string, unknown>
    ).addressCountry = "GB";
    expect(codes(nonUs)).toContain("OMW-W061");
    expect(codes(stnl())).not.toContain("OMW-W061"); // US base
  });

  test("US address-shape: a mis-extracted address → OMW-W062/W063/W064; a good one is clean", () => {
    const bad = stnl();
    (bad.property as Record<string, unknown>).address = {
      streetAddress: "8335 NORTH TELEGRAPH ROAD, NEWPORT, MI 48166", // dup -> W064
      addressLocality: "Michigan", // a state in the city field -> W063
      addressRegion: "Midwest", // a census region, not a state -> W062
      postalCode: "48166",
      addressCountry: "US",
    };
    const c = codes(bad);
    expect(c).toContain("OMW-W062");
    expect(c).toContain("OMW-W063");
    expect(c).toContain("OMW-W064");
    const good = stnl();
    (good.property as Record<string, unknown>).address = {
      streetAddress: "8335 North Telegraph Road",
      addressLocality: "Newport",
      addressRegion: "MI",
      postalCode: "48166",
      addressCountry: "US",
    };
    expect(codes(good).some((x) => ["OMW-W062", "OMW-W063", "OMW-W064"].includes(x))).toBe(false);
  });

  test("the valid sample is internally consistent (no warnings)", () => {
    const r = consistencyFindings(stnl());
    expect(r.warnings).toEqual([]);
    // The sample omits `currency`, so the only info is the USD-default notice (OMI-I001).
    expect(r.info.map((i) => i.code)).toEqual(["OMI-I001"]);
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

  test("OMW-W014 non-positive noi", () => {
    const p = stnl();
    deal(p).noi = -5000;
    expect(codes(p)).toContain("OMW-W014");
  });

  test("OMW-W013 cap rate outside plausibility band", () => {
    const p = stnl();
    deal(p).capRate = 0.3;
    deal(p).noi = 555000; // 555000/1850000 = 0.30 keeps W010 quiet
    expect(codes(p)).toContain("OMW-W013");
  });

  test("OMW-W012 pro-forma without noiAsOfDate", () => {
    const p = stnl();
    deal(p).noiType = "pro-forma";
    delete deal(p).noiAsOfDate;
    expect(codes(p)).toContain("OMW-W012");
  });

  test("OMW-W030 remaining-term mismatch / OMW-W031 lease-term mismatch", () => {
    const term = stnl();
    (term.lease as Record<string, unknown>).termMonths = 60; // vs ~180
    expect(codes(term)).toContain("OMW-W031");
    const rem = stnl();
    (rem.lease as Record<string, unknown>).remainingTermMonths = 12; // vs ~92
    expect(codes(rem)).toContain("OMW-W030");
  });

  test("OMW-W032 assertedDate in the future vs processing date", () => {
    const p = stnl(); // assertedDate 2026-08-15
    expect(
      consistencyFindings(p, undefined, { asOf: "2020-01-01" }).warnings.map((w) => w.code),
    ).toContain("OMW-W032");
    expect(codes(p)).not.toContain("OMW-W032"); // silent without a processing date
  });

  test("OMW-W033 noiAsOfDate after assertedDate", () => {
    const p = stnl();
    deal(p).noiAsOfDate = "2027-01-01";
    expect(codes(p)).toContain("OMW-W033");
  });

  test("OMW-W034 expiration on or before commencement", () => {
    const p = stnl();
    (p.lease as Record<string, unknown>).expiration = "2010-01-01";
    expect(codes(p)).toContain("OMW-W034");
  });

  test("OMW-W041 gross lease with no responsibilities", () => {
    const p = stnl();
    (p.lease as Record<string, unknown>).leaseTypeAsserted = "gross";
    expect(codes(p)).toContain("OMW-W041");
  });

  test("OMW-W050 self-supersede (own hash minus the pointer)", async () => {
    const { payloadHash } = await import("../src/hash.js");
    const p = stnl();
    const stripped = JSON.parse(JSON.stringify(p)) as Record<string, unknown>;
    delete (stripped.meta as Record<string, unknown>).supersedes;
    (p.meta as Record<string, unknown>).supersedes = payloadHash(stripped);
    expect(codes(p)).toContain("OMW-W050");
  });

  test("OMW-W060 source verified without corroborating metadata", () => {
    const p = stnl();
    period(p, 0).source = "verified";
    expect(codes(p)).toContain("OMW-W060");
  });

  test("OMI-I001 currency defaulted; suppressed when present", () => {
    expect(consistencyFindings(stnl()).info.map((i) => i.code)).toContain("OMI-I001");
    const p = stnl();
    p.currency = "USD";
    expect(consistencyFindings(p).info.map((i) => i.code)).not.toContain("OMI-I001");
  });

  test("OMI-I002 source tag absent", () => {
    const p = stnl();
    delete period(p, 0).source;
    expect(consistencyFindings(p).info.map((i) => i.code)).toContain("OMI-I002");
  });

  test("OMI-I003 cross-check skipped for absent inputs", () => {
    const p = stnl();
    delete deal(p).noi;
    delete deal(p).noiType;
    delete deal(p).noiAsOfDate;
    expect(consistencyFindings(p).info.map((i) => i.code)).toContain("OMI-I003");
  });
});

describe("round — banker's rounding parity with Python's round()", () => {
  test("ties round to even (not half-up), matching the Python core", () => {
    // Python: round(0.5)=0, round(1.5)=2, round(2.5)=2, round(3.5)=4, round(-2.5)=-2
    expect(round(0.5, 0)).toBe(0);
    expect(round(1.5, 0)).toBe(2);
    expect(round(2.5, 0)).toBe(2);
    expect(round(3.5, 0)).toBe(4);
    expect(round(-2.5, 0)).toBe(-2);
    // Python: round(0.125,2)=0.12, round(0.375,2)=0.38
    expect(round(0.125, 2)).toBe(0.12);
    expect(round(0.375, 2)).toBe(0.38);
    // non-tie values are unaffected
    expect(round(0.06251, 4)).toBe(0.0625);
  });
});
