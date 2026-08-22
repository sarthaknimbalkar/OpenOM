import { beforeEach, describe, expect, test, vi } from "vitest";
import {
  getSettings,
  getWebhook,
  setWebhook,
  setLinkBadging,
  isLinkBadgingDomain,
} from "../../src/storage.js";
import { refetchPdf, refetchPdfResult } from "../../src/detect.js";
import { guardedMirrorFetch, mirrorUrlFor } from "../../src/mirror.js";

function fakeChrome() {
  const store: Record<string, unknown> = {};
  const syncSet = vi.fn();
  return {
    store,
    syncSet,
    chrome: {
      storage: {
        local: {
          get: async (k: string) => ({ [k]: store[k] }),
          set: async (o: Record<string, unknown>) => Object.assign(store, o),
        },
        sync: { set: syncSet, get: vi.fn() },
      },
    },
  };
}

function resp(
  body: Uint8Array,
  ok = true,
  headers: Record<string, string> = {},
): Response {
  return {
    ok,
    headers: { get: (k: string) => headers[k.toLowerCase()] ?? null },
    // A real ReadableStream so refetchPdf exercises its streaming byte-cap path (#67).
    body: new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(body);
        c.close();
      },
    }),
    arrayBuffer: async () => body.buffer,
  } as unknown as Response;
}

const PDF = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d]); // %PDF-

describe("storage - chrome.storage.local only", () => {
  beforeEach(() => {
    const f = fakeChrome();
    (globalThis as unknown as { chrome: unknown }).chrome = f.chrome;
    (globalThis as unknown as { __sync: unknown }).__sync = f.syncSet;
  });

  test("setWebhook round-trips via local, never sync", async () => {
    await setWebhook({ url: "https://hooks.example.com/x", secret: "s" });
    expect(await getWebhook()).toEqual({
      url: "https://hooks.example.com/x",
      secret: "s",
    });
    expect(
      (globalThis as unknown as { __sync: ReturnType<typeof vi.fn> }).__sync,
    ).not.toHaveBeenCalled();
  });

  test("settings default when unset", async () => {
    expect(await getSettings()).toEqual({
      proactiveDetection: false,
      linkBadgingDomains: [],
    });
  });

  test("link-badging allowlist add/remove/dedup (#69)", async () => {
    await setLinkBadging("buildout.com", true);
    await setLinkBadging("buildout.com", true); // dedup
    expect(await isLinkBadgingDomain("buildout.com")).toBe(true);
    expect((await getSettings()).linkBadgingDomains).toEqual(["buildout.com"]);
    await setLinkBadging("buildout.com", false);
    expect(await isLinkBadgingDomain("buildout.com")).toBe(false);
  });
});

describe("refetchPdf - re-fetch bytes, size-capped", () => {
  test("returns bytes for a normal PDF", async () => {
    const got = await refetchPdf("https://h/x.pdf", 1000, async () =>
      resp(PDF),
    );
    expect(got).toEqual(PDF);
  });
  test("null when over the byte cap", async () => {
    const big = new Uint8Array(2000);
    expect(
      await refetchPdf("https://h/x.pdf", 1000, async () => resp(big)),
    ).toBeNull();
  });
  test("streams and caps a body with NO content-length header (#67)", async () => {
    const big = new Uint8Array(2000); // no content-length → old code buffered it all before checking
    expect(
      await refetchPdf("https://h/x.pdf", 1000, async () => resp(big)),
    ).toBeNull();
    const ok = new Uint8Array([1, 2, 3]);
    expect(
      await refetchPdf("https://h/x.pdf", 1000, async () => resp(ok)),
    ).toEqual(ok);
  });
  test("null when declared content-length exceeds the cap", async () => {
    const got = await refetchPdf("https://h/x.pdf", 1000, async () =>
      resp(PDF, true, { "content-length": "9999" }),
    );
    expect(got).toBeNull();
  });
  test("null on network error", async () => {
    expect(
      await refetchPdf("https://h/x.pdf", 1000, async () => {
        throw new Error("net");
      }),
    ).toBeNull();
  });
  test("[M6] refetchPdfResult distinguishes oversize from fetch-failure and success", async () => {
    const ok = await refetchPdfResult("https://h/x.pdf", 1000, async () => resp(PDF));
    expect(ok).toEqual({ ok: true, bytes: PDF });
    const big = await refetchPdfResult("https://h/x.pdf", 1000, async () => resp(new Uint8Array(2000)));
    expect(big).toEqual({ ok: false, reason: "oversize" });
    const declared = await refetchPdfResult("https://h/x.pdf", 1000, async () =>
      resp(PDF, true, { "content-length": "9999" }),
    );
    expect(declared).toEqual({ ok: false, reason: "oversize" });
    const neterr = await refetchPdfResult("https://h/x.pdf", 1000, async () => {
      throw new Error("net");
    });
    expect(neterr).toEqual({ ok: false, reason: "fetch" });
  });
  test("#122 SSRF: refuses an internal/metadata target WITHOUT fetching", async () => {
    const spy = vi.fn(async () => resp(PDF));
    for (const url of [
      "https://169.254.169.254/x.pdf",
      "https://[0:0:0:0:0:0:0:1]/x.pdf",
      "http://h/x.pdf",
    ]) {
      expect(await refetchPdf(url, 1000, spy)).toBeNull();
    }
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("mirror", () => {
  test("mirrorUrlFor derives sibling om.json", () => {
    expect(mirrorUrlFor("https://h.example.com/dir/deal.pdf")).toBe(
      "https://h.example.com/dir/om.json",
    );
  });
  test("guardedMirrorFetch rejects non-https", async () => {
    expect(
      await guardedMirrorFetch("http://h/om.json", 1000, async () => resp(PDF)),
    ).toBeNull();
  });
  test("guardedMirrorFetch returns body for https", async () => {
    const r = await guardedMirrorFetch("https://h/om.json", 1000, async () =>
      resp(PDF),
    );
    expect(r).toEqual({ https: true, body: PDF });
  });
  test("#122 SSRF: guardedMirrorFetch refuses an internal target WITHOUT fetching", async () => {
    const spy = vi.fn(async () => resp(PDF));
    expect(
      await guardedMirrorFetch("https://[::1]/om.json", 1000, spy),
    ).toBeNull();
    expect(
      await guardedMirrorFetch("https://192.168.0.1/om.json", 1000, spy),
    ).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });
});
