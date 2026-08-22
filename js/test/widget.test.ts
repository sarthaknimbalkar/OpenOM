import { describe, expect, test } from "vitest";
import {
  computeBadge,
  evaluateBadge,
  viewForState,
  clearBadgeCache,
  readByUrl,
  type BadgeOptions,
} from "../widget/badge-core.js";
import { beforeEach } from "vitest";
import { FORBIDDEN } from "../src/badge.js";
import { embedPayload } from "../src/embed.js";
import { preimageBytes } from "../src/hash.js";
import { PDFDocument } from "pdf-lib";

async function blankPdfBytes(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  doc.addPage([200, 200]);
  return doc.save();
}

// #144: the embeddable badge is honesty-critical - it must map provenance to the §AA state exactly
// like the extension (shared openom-js core) and never overclaim. These cover the pure core; the DOM
// shell is a thin wrapper that only renders these static strings.

describe("computeBadge (§AA precedence + honesty)", () => {
  test("absent → nothing to show, no aria", () => {
    const v = computeBadge({
      present: false,
      hashValid: null,
      originVerified: false,
      signatureValid: null,
    });
    expect(v.state).toBe("absent");
    expect(v.ariaLabel).toBe("");
    expect(v.honest).toBe(true);
    // [polish] neutral caption for generic consumers - no author-only "vision fallback" wording.
    expect(v.caption.toLowerCase()).not.toContain("vision");
    expect(v.caption).toBe("No embedded openOM data in this PDF.");
  });
  test("hash mismatch is terminal even if origin would pass", () => {
    const v = computeBadge({
      present: true,
      hashValid: false,
      originVerified: true,
      signatureValid: null,
    });
    expect(v.state).toBe("hash-mismatch");
    expect(v.label.toLowerCase()).toContain("altered");
  });
  test("integrity-ok never uses a FORBIDDEN word (no overclaim)", () => {
    const v = computeBadge({
      present: true,
      hashValid: true,
      originVerified: false,
      signatureValid: null,
    });
    expect(v.state).toBe("integrity-ok");
    expect(v.honest).toBe(true);
    const text = (v.label + " " + v.caption).toLowerCase();
    for (const w of FORBIDDEN) expect(text).not.toContain(w);
  });
  test("origin-verified only when integrity AND origin pass", () => {
    expect(
      computeBadge({ present: true, hashValid: true, originVerified: true, signatureValid: null })
        .state,
    ).toBe("origin-verified");
  });
});

describe("evaluateBadge (read pipeline)", () => {
  const payload = { "@type": "RealEstateListing", specVersion: "0.1", assertedBy: { broker: "A" } };
  beforeEach(() => clearBadgeCache());

  function fetchReturning(bytes: Uint8Array): typeof fetch {
    return (async () => new Response(bytes, { status: 200 })) as unknown as typeof fetch;
  }

  test("a plain PDF (no payload) → absent", async () => {
    const opts: BadgeOptions = {
      src: "https://portal.example.com/plain.pdf",
      fetchImpl: fetchReturning(await blankPdfBytes()),
    };
    expect((await evaluateBadge(opts)).state).toBe("absent");
  });

  test("an embedded, unaltered PDF → integrity-ok (no mirror)", async () => {
    const embedded = await embedPayload(await blankPdfBytes(), payload);
    const v = await evaluateBadge({
      src: "https://portal.example.com/deal.pdf",
      fetchImpl: fetchReturning(embedded),
    });
    expect(v.state).toBe("integrity-ok");
    expect(v.honest).toBe(true);
  });

  test("[M2] a domain mirror with a NEWER assertion → integrity-ok + stale (OMW-W051)", async () => {
    const embedded = await embedPayload(await blankPdfBytes(), {
      ...payload,
      assertedDate: "2026-01-01",
    });
    // The mirror is a newer assertion (exact JCS preimage bytes, as `om mirror` emits).
    const mirror = preimageBytes({ ...payload, assertedDate: "2026-06-01" });
    const byUrl: typeof fetch = (async (u: string) =>
      new Response(u.endsWith(".jsonld") ? mirror : embedded, {
        status: 200,
      })) as unknown as typeof fetch;
    const v = await evaluateBadge({
      src: "https://broker.example.com/deal.pdf",
      mirror: "https://broker.example.com/deal.jsonld",
      fetchImpl: byUrl,
    });
    expect(v.state).toBe("integrity-ok"); // genuine, but…
    expect(v.stale).toBe("OMW-W051"); // …superseded by the newer mirror
    expect(v.mirrorAssertedDate).toBe("2026-06-01");
  });

  test("[#2] the cache is bounded — oldest entries are evicted past the cap", async () => {
    const { setBadgeCacheMax, badgeCacheSize } = await import("../widget/badge-core.js");
    setBadgeCacheMax(2);
    clearBadgeCache();
    const embedded = await embedPayload(await blankPdfBytes(), payload);
    let fetches = 0;
    const f: typeof fetch = (async () => {
      fetches++;
      return new Response(embedded, { status: 200 });
    }) as unknown as typeof fetch;
    await evaluateBadge({ src: "https://p/a.pdf", fetchImpl: f });
    await evaluateBadge({ src: "https://p/b.pdf", fetchImpl: f });
    await evaluateBadge({ src: "https://p/c.pdf", fetchImpl: f }); // evicts a.pdf (cap 2)
    expect(badgeCacheSize()).toBe(2);
    await evaluateBadge({ src: "https://p/a.pdf", fetchImpl: f }); // was evicted → re-fetches
    expect(fetches).toBe(4);
    setBadgeCacheMax(512); // restore default for other tests
  });

  test("[M1] auto-derives the mirror from payload.meta.canonicalUrl → origin-verified (no opts.mirror)", async () => {
    const p = {
      ...payload,
      meta: { supersedes: null, canonicalUrl: "https://broker.example.com/deal.jsonld" },
    };
    const embedded = await embedPayload(await blankPdfBytes(), p);
    const mirror = preimageBytes(p); // the exact JCS payload bytes at canonicalUrl
    const f: typeof fetch = (async (u: string) =>
      new Response(u.endsWith(".jsonld") ? mirror : embedded, {
        status: 200,
      })) as unknown as typeof fetch;
    const v = await evaluateBadge({ src: "https://broker.example.com/deal.pdf", fetchImpl: f });
    expect(v.state).toBe("origin-verified"); // reached ✓✓ from the bytes alone, no per-listing config
  });

  test("[M8] same-domain mirror with DIFFERENT (non-supersede) content → diverged (OMW-W052)", async () => {
    const p = {
      ...payload,
      assertedDate: "2026-01-01",
      deal: { askingPrice: 1000 },
      meta: { supersedes: null, canonicalUrl: "https://broker.example.com/deal.jsonld" },
    };
    const embedded = await embedPayload(await blankPdfBytes(), p);
    // Mirror: same domain, same/older date, different figures, NOT a supersede.
    const mirror = preimageBytes({ ...p, deal: { askingPrice: 9999 } });
    const f: typeof fetch = (async (u: string) =>
      new Response(u.endsWith(".jsonld") ? mirror : embedded, {
        status: 200,
      })) as unknown as typeof fetch;
    const v = await evaluateBadge({ src: "https://broker.example.com/deal.pdf", fetchImpl: f });
    expect(v.state).toBe("integrity-ok"); // integrity holds…
    expect(v.diverged).toBe("OMW-W052"); // …but the source domain shows different figures
    expect(v.stale).toBeUndefined();
  });

  test("[B1] caches by src|mirror — N badges for the same PDF fetch once", async () => {
    const embedded = await embedPayload(await blankPdfBytes(), payload);
    let fetches = 0;
    const counting: typeof fetch = (async () => {
      fetches++;
      return new Response(embedded, { status: 200 });
    }) as unknown as typeof fetch;
    const opts = { src: "https://portal.example.com/same.pdf", fetchImpl: counting };
    const [a, b, c] = await Promise.all([
      evaluateBadge(opts),
      evaluateBadge(opts),
      evaluateBadge(opts),
    ]);
    expect(fetches).toBe(1); // deduped in-flight + cached
    expect(a.state).toBe("integrity-ok");
    expect(b).toBe(a);
    expect(c).toBe(a);
  });
});

describe("readByUrl ([#1] single source for /verify + /v/; [#5] direct + worker fallback)", () => {
  const payload = { "@type": "RealEstateListing", specVersion: "0.1", assertedBy: { broker: "A" } };

  test("direct fetch success (same-origin/CORS host) — never calls the worker", async () => {
    const embedded = await embedPayload(await blankPdfBytes(), payload);
    let workerCalls = 0;
    const f: typeof fetch = (async (u: string) => {
      if (u.includes("mcp.openom.app")) workerCalls++;
      return new Response(embedded, { status: 200 });
    }) as unknown as typeof fetch;
    const r = await readByUrl("https://same.example.com/deal.pdf", { fetchImpl: f });
    expect(r.state).toBe("present");
    expect(r.verification.hashValid).toBe(true);
    expect(workerCalls).toBe(0);
  });

  test("direct fetch blocked (CORS throw) → falls back to the worker om_read", async () => {
    const inner = JSON.stringify({
      state: "present",
      payload: { deal: { askingPrice: 1 } },
      verification: { hashValid: true, signatureValid: null },
    });
    const f: typeof fetch = (async (_u: string, init?: RequestInit) => {
      if (!init) throw new TypeError("CORS blocked"); // the direct GET
      return new Response(JSON.stringify({ result: { content: [{ text: inner }] } }), {
        status: 200,
      });
    }) as unknown as typeof fetch;
    const r = await readByUrl("https://cdn.other.com/deal.pdf", {
      fetchImpl: f,
      endpoint: "https://mcp.openom.app/mcp",
    });
    expect(r.state).toBe("present");
    expect(r.payload).toEqual({ deal: { askingPrice: 1 } });
  });

  test("worker tool error surfaces the message", async () => {
    const f: typeof fetch = (async (_u: string, init?: RequestInit) => {
      if (!init) throw new TypeError("CORS");
      return new Response(
        JSON.stringify({
          result: { isError: true, content: [{ text: "Error: PDF exceeds the size limit" }] },
        }),
        { status: 200 },
      );
    }) as unknown as typeof fetch;
    await expect(readByUrl("https://cdn.other.com/big.pdf", { fetchImpl: f })).rejects.toThrow(
      /size limit/,
    );
  });

  test("a non-https fallback target throws locally (no worker call)", async () => {
    let workerCalls = 0;
    const f: typeof fetch = (async (u: string) => {
      if (u.includes("mcp.openom.app")) workerCalls++;
      if (u.startsWith("http://")) return new Response("nope", { status: 404 }); // direct !ok
      return new Response("x", { status: 404 });
    }) as unknown as typeof fetch;
    await expect(readByUrl("http://insecure.example.com/x.pdf", { fetchImpl: f })).rejects.toThrow(
      /https/,
    );
    expect(workerCalls).toBe(0);
  });
});

describe("viewForState ([B1] precomputed, zero-fetch)", () => {
  test("renders honest labels for each known state without any fetch", () => {
    expect(viewForState("integrity-ok").state).toBe("integrity-ok");
    expect(viewForState("integrity-ok").honest).toBe(true);
    expect(viewForState("origin-verified").state).toBe("origin-verified");
    expect(viewForState("hash-mismatch").label.toLowerCase()).toContain("altered");
    // integrity-ok must not overclaim even via the precomputed path.
    const t = (
      viewForState("integrity-ok").label +
      " " +
      viewForState("integrity-ok").caption
    ).toLowerCase();
    for (const w of FORBIDDEN) expect(t).not.toContain(w);
  });
  test("unknown/absent → renders nothing (no false reassurance)", () => {
    expect(viewForState("absent").state).toBe("absent");
    expect(viewForState("garbage").state).toBe("absent");
    expect(viewForState("absent").ariaLabel).toBe("");
  });
});
