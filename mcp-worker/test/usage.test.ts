import { describe, expect, test } from "vitest";
import { hostBucket, hostOf, usagePoint } from "../src/usage.js";

describe("usage (privacy-preserving aggregate metrics)", () => {
  test("hostOf extracts a lowercased hostname, else null", () => {
    expect(hostOf("https://CDN.Example.com/deal.pdf")).toBe("cdn.example.com");
    expect(hostOf(undefined)).toBeNull(); // pdfBase64 read has no host
    expect(hostOf("not a url")).toBeNull();
  });

  test("hostBucket is a stable 16-bit hex, salt-dependent, and hides the domain", async () => {
    const a = await hostBucket("cdn.example.com", "salt1");
    const b = await hostBucket("cdn.example.com", "salt1");
    expect(a).toBe(b); // deterministic -> distinct-count is stable within a dataset
    expect(a).toMatch(/^[0-9a-f]{4}$/); // 16 bits, 4 hex chars
    const salted = await hostBucket("cdn.example.com", "salt2");
    expect(salted).not.toBe(a); // a different salt reshuffles the buckets
    // The bucket is not the domain and does not contain it.
    expect(a).not.toContain("example");
  });

  test("usagePoint carries the dimensions; host bucket is appended only when present", () => {
    expect(usagePoint("om_read", "present", "a1b2")).toEqual({
      blobs: ["om_read", "present", "a1b2"],
      doubles: [1],
      indexes: ["om_read"],
    });
    // A hostless read (pdfBase64) records no bucket - no domain signal at all.
    expect(usagePoint("om_read", "absent", null).blobs).toEqual(["om_read", "absent"]);
  });
});
