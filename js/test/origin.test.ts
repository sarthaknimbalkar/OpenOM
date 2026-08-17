import { describe, expect, test } from "vitest";
import { integrityHashOfBytes } from "../src/verify.js";
import { type MirrorFetch, verifyOrigin } from "../src/origin.js";

const BODY = new TextEncoder().encode('{"@type":"RealEstateListing","specVersion":"0.1"}');
const HASH = integrityHashOfBytes(BODY);

const serve =
  (body: Uint8Array, https = true): MirrorFetch =>
  async () => ({ https, body });
const unreachable: MirrorFetch = async () => null;

describe("verifyOrigin — §10.1", () => {
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
