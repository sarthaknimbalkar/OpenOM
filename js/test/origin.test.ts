import { describe, expect, test } from "vitest";
import { integrityHashOfBytes } from "../src/verify.js";
import { type MirrorFetch, verifyOrigin } from "../src/origin.js";

const BODY = new TextEncoder().encode('{"@type":"RealEstateListing","specVersion":"0.1"}');
const HASH = integrityHashOfBytes(BODY);

const serve =
  (body: Uint8Array, https = true): MirrorFetch =>
  async () => ({ https, body });
const unreachable: MirrorFetch = async () => null;

describe("verifyOrigin - §10.1", () => {
  test("same domain + matching hash → origin-verified", async () => {
    const r = await verifyOrigin({
      sourceUrl: "https://broker.example.com/deal.pdf",
      mirrorUrl: "https://broker.example.com/om.json",
      embeddedHash: HASH,
      fetchMirror: serve(BODY),
    });
    expect(r.originVerified).toBe(true);
  });

  test("cross eTLD+1 → origin-unverified, graceful (A5 rehost)", async () => {
    const r = await verifyOrigin({
      sourceUrl: "https://attacker.net/deal.pdf",
      mirrorUrl: "https://broker.example.com/om.json",
      embeddedHash: HASH,
      fetchMirror: serve(BODY),
    });
    expect(r.originVerified).toBe(false);
    expect(r.reason).toBe("cross-origin");
  });

  test("same domain, different hash → unverified (stale/superseded)", async () => {
    const r = await verifyOrigin({
      sourceUrl: "https://broker.example.com/deal.pdf",
      mirrorUrl: "https://broker.example.com/om.json",
      embeddedHash: "sha256:" + "0".repeat(64),
      fetchMirror: serve(BODY),
    });
    expect(r.originVerified).toBe(false);
    expect(r.reason).toBe("hash-mismatch");
  });

  test("non-https source or mirror → unverified", async () => {
    const r = await verifyOrigin({
      sourceUrl: "http://broker.example.com/deal.pdf",
      mirrorUrl: "https://broker.example.com/om.json",
      embeddedHash: HASH,
      fetchMirror: serve(BODY),
    });
    expect(r.originVerified).toBe(false);
    expect(r.reason).toBe("not-https");
  });

  test("mirror unreachable → unverified", async () => {
    const r = await verifyOrigin({
      sourceUrl: "https://broker.example.com/deal.pdf",
      mirrorUrl: "https://broker.example.com/om.json",
      embeddedHash: HASH,
      fetchMirror: unreachable,
    });
    expect(r.originVerified).toBe(false);
    expect(r.reason).toBe("unreachable");
  });

  test("multi-part TLD: subdomain vs apex share the registrable domain", async () => {
    const r = await verifyOrigin({
      sourceUrl: "https://x.example.co.uk/deal.pdf",
      mirrorUrl: "https://example.co.uk/om.json",
      embeddedHash: HASH,
      fetchMirror: serve(BODY),
    });
    expect(r.originVerified).toBe(true);
  });
});

describe("verifyOrigin - hash format normalization (#81)", () => {
  const args = (embeddedHash: string) => ({
    sourceUrl: "https://broker.example.com/deal.pdf",
    mirrorUrl: "https://broker.example.com/om.json",
    embeddedHash,
    fetchMirror: serve(BODY),
  });
  test("uppercase-hex embedded hash still verifies", async () => {
    expect((await verifyOrigin(args(HASH.toUpperCase()))).originVerified).toBe(true);
  });
  test("unprefixed digest (no sha256:) still verifies", async () => {
    expect((await verifyOrigin(args(HASH.replace(/^sha256:/, "")))).originVerified).toBe(true);
  });
  test("whitespace-padded embedded hash still verifies", async () => {
    expect((await verifyOrigin(args(`  ${HASH}  `))).originVerified).toBe(true);
  });
  test("a genuinely different digest still mismatches", async () => {
    expect((await verifyOrigin(args("sha256:" + "b".repeat(64)))).originVerified).toBe(false);
  });
});

describe("verifyOrigin - multi-label eTLD+1 via the PSL (#80)", () => {
  const check = (source: string, mirror: string) =>
    verifyOrigin({
      sourceUrl: source,
      mirrorUrl: mirror,
      embeddedHash: HASH,
      fetchMirror: serve(BODY),
    });

  test("same registrable domain under a ccSLD (foo.co.uk) verifies", async () => {
    expect(
      (await check("https://foo.co.uk/deal.pdf", "https://foo.co.uk/om.json")).originVerified,
    ).toBe(true);
    expect(
      (await check("https://www.foo.co.uk/deal.pdf", "https://foo.co.uk/om.json")).originVerified,
    ).toBe(true);
  });
  test("different registrable domains under a ccSLD are cross-origin", async () => {
    expect((await check("https://foo.co.uk/deal.pdf", "https://bar.co.uk/om.json")).reason).toBe(
      "cross-origin",
    );
  });
  test("*.github.io is a public suffix - distinct users are cross-origin", async () => {
    expect(
      (await check("https://a.github.io/deal.pdf", "https://b.github.io/om.json")).reason,
    ).toBe("cross-origin");
  });
});
