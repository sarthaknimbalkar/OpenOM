import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, test, vi } from "vitest";
import { fetchPdf, safeUrl, readCapped, ByteBudget } from "../src/index.js";

// The shared cross-implementation SSRF deny-vectors (spec/vectors/ssrf-deny.json), the same list the
// Python guard tests against - so a bypass added there is forced onto the Worker guard too.
const ssrfDeny = JSON.parse(
  readFileSync(fileURLToPath(new URL("../../spec/vectors/ssrf-deny.json", import.meta.url)), "utf-8"),
) as { blocked_ips: { ip: string; why: string }[]; blocked_hosts: { host: string; why: string }[] };

// A fake fetch that plays back a scripted sequence of responses keyed by call order, recording URLs.
function scriptedFetch(steps: Array<{ status: number; location?: string; body?: Uint8Array }>) {
  const seen: string[] = [];
  let i = 0;
  const impl = (async (url: string) => {
    seen.push(url);
    const s = steps[Math.min(i++, steps.length - 1)]!;
    const headers = new Headers();
    if (s.location) headers.set("location", s.location);
    const body = s.body ?? new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d]); // %PDF-
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

  test("refuses every shared cross-impl SSRF deny-vector", () => {
    for (const { ip, why } of ssrfDeny.blocked_ips) {
      const host = ip.includes(":") ? `[${ip}]` : ip; // bracket IPv6 literals
      expect(() => safeUrl(`https://${host}/x`), `${ip} (${why})`).toThrow();
    }
    for (const { host, why } of ssrfDeny.blocked_hosts) {
      expect(() => safeUrl(`https://${host}/x`), `${host} (${why})`).toThrow();
    }
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

  test("refuses a fetched non-PDF body (no general-GET oracle), matching fetch.py", async () => {
    const html = new TextEncoder().encode("<!doctype html><html>not a pdf</html>");
    const { impl } = scriptedFetch([{ status: 200, body: html }]);
    await expect(fetchPdf("https://example.com/", impl)).rejects.toThrow(/not a PDF|%PDF/);
    // a real PDF body still passes
    const pdf = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31]); // %PDF-1
    const ok = scriptedFetch([{ status: 200, body: pdf }]);
    expect(Array.from(await fetchPdf("https://cdn.example.com/a.pdf", ok.impl))).toEqual(
      Array.from(pdf),
    );
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
    expect(await codeOf(fetchPdf("http://x.example.com/a.pdf"))).toBe("OM-IO-008");
    expect(await codeOf(fetchPdf("https://127.0.0.1/a.pdf"))).toBe("OM-IO-002");
    const big = scriptedFetch([{ status: 200, body: new Uint8Array(30_000_000) }]);
    expect(await codeOf(fetchPdf("https://cdn.example.com/big.pdf", big.impl))).toBe("OM-IO-005");
    const bad = scriptedFetch([{ status: 404 }]);
    expect(await codeOf(fetchPdf("https://cdn.example.com/missing.pdf", bad.impl))).toBe("OM-IO-001");
    const loop = scriptedFetch([{ status: 302, location: "https://a.example.com/n" }]);
    expect(await codeOf(fetchPdf("https://cdn.example.com/x.pdf", loop.impl))).toBe("OM-IO-009");
  });
});


describe("ByteBudget bounds total outbound bytes across a request", () => {
  test("charges each fetch and refuses once the shared budget is exhausted", async () => {
    const pdf = new Uint8Array(1000).fill(0x25);
    pdf.set([0x25, 0x50, 0x44, 0x46, 0x2d], 0); // %PDF- header so the content sniff passes
    const budget = new ByteBudget(2500); // room for two 1000-byte reads, not a third
    const one = scriptedFetch([{ status: 200, body: pdf }]);
    await fetchPdf("https://cdn.example.com/a.pdf", one.impl, budget);
    expect(budget.remaining).toBe(1500);
    const two = scriptedFetch([{ status: 200, body: pdf }]);
    await fetchPdf("https://cdn.example.com/b.pdf", two.impl, budget);
    expect(budget.remaining).toBe(500);
    // The next fetch's cap is now only 500; a 1000-byte body must abort mid-stream.
    const three = scriptedFetch([{ status: 200, body: pdf }]);
    await expect(fetchPdf("https://cdn.example.com/c.pdf", three.impl, budget)).rejects.toThrow(
      /size limit/,
    );
  });

  test("without a budget the per-fetch cap still applies (back-compat)", async () => {
    const pdf = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31]); // %PDF-1
    const { impl } = scriptedFetch([{ status: 200, body: pdf }]);
    const out = await fetchPdf("https://cdn.example.com/a.pdf", impl);
    expect(out.length).toBe(6);
  });

  test("admission control: CONCURRENT fetches can't collectively exceed the shared budget", async () => {
    // Round-3 DoS: with post-hoc charging, 20 concurrent fetches each saw the full budget and
    // buffered their body before any charge landed. Reserve-then-refund caps total admitted bytes to
    // the budget: with a 2500-byte budget and 1000-byte bodies, at most 2 can succeed.
    const body = new Uint8Array(1000).fill(0x25);
    body.set([0x25, 0x50, 0x44, 0x46, 0x2d], 0); // %PDF-
    const budget = new ByteBudget(2500);
    const results = await Promise.allSettled(
      Array.from({ length: 20 }, (_, i) => {
        const { impl } = scriptedFetch([{ status: 200, body }]);
        return fetchPdf(`https://cdn.example.com/${i}.pdf`, impl, budget);
      }),
    );
    const ok = results.filter((r) => r.status === "fulfilled").length;
    expect(ok).toBeLessThanOrEqual(2); // total admitted bytes (ok * 1000) never exceeds the 2500 budget
    expect(budget.remaining).toBeLessThanOrEqual(2500); // and the budget is never overdrawn
    expect(budget.remaining).toBeGreaterThanOrEqual(0);
  });
});

describe("[Mi5] readCapped aborts an oversize/unknown-length body", () => {

  function streamOf(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
    let i = 0;
    return new ReadableStream({
      pull(c) {
        if (i < chunks.length) c.enqueue(chunks[i++]);
        else c.close();
      },
    });
  }

  test("throws OM-IO-005 as soon as the cap is exceeded (never buffers the whole body)", async () => {
    const chunks = Array.from({ length: 5 }, () => new Uint8Array(4)); // 20 bytes total
    await expect(readCapped(streamOf(chunks), 10)).rejects.toThrow(/size limit/);
  });

  test("returns the assembled bytes when under the cap", async () => {
    const out = await readCapped(streamOf([new Uint8Array([1, 2]), new Uint8Array([3])]), 100);
    expect(Array.from(out)).toEqual([1, 2, 3]);
  });
});
