import { describe, expect, test } from "vitest";
import {
  computeBadge,
  evaluateBadge,
  viewForState,
  clearBadgeCache,
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
