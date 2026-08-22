import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, test } from "vitest";
import { summarizeDeal } from "../src/summary.js";

const stnl = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "spec", "samples", "valid-stnl.json"), "utf8"),
);

describe("summarizeDeal ([M3] consumer read API)", () => {
  test("flattens + formats the sample deal (currency-aware, cap rate as %)", () => {
    const s = summarizeDeal(stnl);
    expect(s.address).toContain("1000 Example Rd");
    expect(s.askingPrice).toBe(1_850_000);
    expect(s.askingPriceText).toMatch(/\$1,850,000/);
    expect(s.capRate).toBe(0.0625);
    expect(s.capRateText).toBe("6.25%"); // not a bare 0.0625
    expect(s.noiType).toBe("in-place");
    expect(s.noiAsOfDate).toBe("2026-06-30"); // assertion metadata carried
    expect(s.tenant).toBe("Example Retail Stores, LLC");
    expect(s.assertedByBroker).toBe("Jane Example");
    expect(s.assertedDate).toBe("2026-08-15");
  });

  test("missing fields are null, never NaN or undefined", () => {
    const s = summarizeDeal({});
    expect(s.askingPrice).toBeNull();
    expect(s.askingPriceText).toBeNull();
    expect(s.capRateText).toBeNull();
    expect(s.tenant).toBeNull();
    expect(s.currency).toBe("USD");
  });

  test("honors a non-USD currency from the payload", () => {
    const s = summarizeDeal({ currency: "EUR", deal: { askingPrice: 1000000 } });
    expect(s.currency).toBe("EUR");
    expect(s.askingPriceText).toMatch(/€|EUR/);
  });
});
