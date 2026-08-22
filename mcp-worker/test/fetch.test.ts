import { describe, expect, test, vi } from "vitest";
import { fetchPdf, safeUrl } from "../src/index.js";

// A fake fetch that plays back a scripted sequence of responses keyed by call order, recording URLs.
function scriptedFetch(steps: Array<{ status: number; location?: string; body?: Uint8Array }>) {
  const seen: string[] = [];
  let i = 0;
  const impl = (async (url: string) => {
    seen.push(url);
    const s = steps[Math.min(i++, steps.length - 1)]!;
    const headers = new Headers();
    if (s.location) headers.set("location", s.location);
    const body = s.body ?? new Uint8Array([0x25, 0x50, 0x44, 0x46]); // %PDF
    return {
      status: s.status,
      ok: s.status >= 200 && s.status < 300,
      headers,
      arrayBuffer: async () => body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength),
    } as unknown as Response;
  }) as unknown as typeof fetch;
  return { impl, seen };
}

describe("safeUrl (SSRF guard)", () => {
  test("allows https public hosts, refuses non-https + internal targets", () => {
    expect(safeUrl("https://cdn.example.com/deal.pdf").hostname).toBe("cdn.example.com");
    expect(() => safeUrl("http://cdn.example.com/deal.pdf")).toThrow(/https/);
    for (const bad of [
      "https://localhost/x",
      "https://app.localhost/x",
      "https://127.0.0.1/x",
      "https://169.254.169.254/latest/meta-data",
      "https://10.0.0.5/x",
      "https://192.168.1.1/x",
      "https://172.16.0.1/x",
      "https://172.31.255.1/x",
      "https://foo.internal/x",
      "https://metadata.google.internal/x",
      "https://0.0.0.0/x",
      "https://100.64.0.1/x", // CGNAT
      "https://[::1]/x", // IPv6 loopback
      "https://[::]/x", // IPv6 unspecified
      "https://[fd00::1]/x", // IPv6 ULA
      "https://[fe80::1]/x", // IPv6 link-local
      "https://[::ffff:169.254.169.254]/x", // IPv4-mapped metadata
    ]) {
      expect(() => safeUrl(bad), bad).toThrow();
    }
    // Public hosts (incl. a public IPv6) still pass.
    expect(safeUrl("https://[2606:4700::1111]/x").hostname).toContain("2606");
  });
});

describe("fetchPdf ([#36] follow bounded, re-pinned redirects)", () => {
  test("follows a presigned-style redirect to the signed asset", async () => {
    const pdf = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31]); // %PDF-1
    const { impl, seen } = scriptedFetch([
      { status: 302, location: "https://signed.s3.example.com/abc?sig=1" },
      { status: 200, body: pdf },
    ]);
    const out = await fetchPdf("https://cdn.example.com/listing/123/download", impl);
    expect(Array.from(out)).toEqual(Array.from(pdf));
    expect(seen).toEqual([
      "https://cdn.example.com/listing/123/download",
      "https://signed.s3.example.com/abc?sig=1",
    ]);
  });

  test("resolves a RELATIVE Location against the current URL", async () => {
    const { impl, seen } = scriptedFetch([
      { status: 301, location: "/files/deal.pdf" },
      { status: 200 },
    ]);
    await fetchPdf("https://cdn.example.com/l/9", impl);
    expect(seen[1]).toBe("https://cdn.example.com/files/deal.pdf");
  });

  test("re-runs the SSRF guard on the redirect target (blocks redirect->internal)", async () => {
    const { impl } = scriptedFetch([
      { status: 302, location: "https://169.254.169.254/latest/meta-data" },
      { status: 200 },
    ]);
    await expect(fetchPdf("https://cdn.example.com/deal.pdf", impl)).rejects.toThrow(
      /internal|loopback/i,
    );
  });

  test("refuses non-https redirect targets", async () => {
    const { impl } = scriptedFetch([
      { status: 302, location: "http://cdn.example.com/deal.pdf" },
      { status: 200 },
    ]);
    await expect(fetchPdf("https://cdn.example.com/deal.pdf", impl)).rejects.toThrow(/https/);
  });

  test("bounds the redirect chain (too many hops -> error, not an infinite loop)", async () => {
    const { impl } = scriptedFetch([{ status: 302, location: "https://a.example.com/next" }]); // always 302
    await expect(fetchPdf("https://cdn.example.com/deal.pdf", impl)).rejects.toThrow(/redirect limit/);
  });

  test("a redirect without a Location is an error, not a hang", async () => {
    const { impl } = scriptedFetch([{ status: 302 }]);
    await expect(fetchPdf("https://cdn.example.com/deal.pdf", impl)).rejects.toThrow(/Location/);
  });

  test("[M4] failures carry a stable machine code, not just prose", async () => {
    const codeOf = async (p: Promise<unknown>): Promise<string | undefined> => {
      try {
        await p;
      } catch (e) {
        return (e as { code?: string }).code;
      }
      return undefined;
    };
    expect(await codeOf(fetchPdf("http://x.example.com/a.pdf"))).toBe("OM-IO-SSRF");
    expect(await codeOf(fetchPdf("https://127.0.0.1/a.pdf"))).toBe("OM-IO-SSRF");
    const big = scriptedFetch([{ status: 200, body: new Uint8Array(30_000_000) }]);
    expect(await codeOf(fetchPdf("https://cdn.example.com/big.pdf", big.impl))).toBe("OM-IO-BOMB");
    const bad = scriptedFetch([{ status: 404 }]);
    expect(await codeOf(fetchPdf("https://cdn.example.com/missing.pdf", bad.impl))).toBe("OM-IO-FETCH");
    const loop = scriptedFetch([{ status: 302, location: "https://a.example.com/n" }]);
    expect(await codeOf(fetchPdf("https://cdn.example.com/x.pdf", loop.impl))).toBe("OM-IO-REDIRECT");
  });
});
