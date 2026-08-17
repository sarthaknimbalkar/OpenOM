import { describe, expect, test } from "vitest";
import { localDateISO } from "../../src/author/clock.js";

describe("localDateISO — local calendar date, not UTC (#64)", () => {
  test("returns the local Y-M-D of a locally-constructed date", () => {
    // new Date(y, m, d, ...) is LOCAL; 23:30 must never roll to the next calendar day.
    expect(localDateISO(new Date(2026, 0, 15, 23, 30))).toBe("2026-01-15");
  });

  test("zero-pads month and day", () => {
    expect(localDateISO(new Date(2026, 2, 5, 9, 0))).toBe("2026-03-05");
  });

  test("matches the platform's own local components (TZ-independent)", () => {
    const d = new Date(2026, 6, 4, 22, 45);
    const expected = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    expect(localDateISO(d)).toBe(expected);
  });
});
