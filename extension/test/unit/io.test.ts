import { beforeEach, describe, expect, test, vi } from "vitest";
import { getSettings, getWebhook, setWebhook } from "../../src/storage.js";
import { refetchPdf } from "../../src/detect.js";
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

function resp(body: Uint8Array, ok = true, headers: Record<string, string> = {}): Response {
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

describe("storage — chrome.storage.local only", () => {
  beforeEach(() => {
    const f = fakeChrome();
    (globalThis as unknown as { chrome: unknown }).chrome = f.chrome;
    (globalThis as unknown as { __sync: unknown }).__sync = f.syncSet;
  });

  test("setWebhook round-trips via local, never sync", async () => {
    await setWebhook({ url: "https://hooks.example.com/x", secret: "s" });
    expect(await getWebhook()).toEqual({ url: "https://hooks.example.com/x", secret: "s" });
    expect((globalThis as unknown as { __sync: ReturnType<typeof vi.fn> }).__sync).not.toHaveBeenCalled();
  });

  test("settings default when unset", async () => {
    expect(await getSettings()).toEqual({ linkBadging: false, proactiveDetection: false });
  });
});

describe("refetchPdf — re-fetch bytes, size-capped", () => {
  test("returns bytes for a normal PDF", async () => {
    const got = await refetchPdf("https://h/x.pdf", 1000, async () => resp(PDF));
    expect(got).toEqual(PDF);
  });
  test("null when over the byte cap", async () => {
    const big = new Uint8Array(2000);
    expect(await refetchPdf("https://h/x.pdf", 1000, async () => resp(big))).toBeNull();
  });
  test("streams and caps a body with NO content-length header (#67)", async () => {
    const big = new Uint8Array(2000); // no content-length → old code buffered it all before checking
    expect(await refetchPdf("https://h/x.pdf", 1000, async () => resp(big))).toBeNull();
    const ok = new Uint8Array([1, 2, 3]);
    expect(await refetchPdf("https://h/x.pdf", 1000, async () => resp(ok))).toEqual(ok);
  });
  test("null when declared content-length exceeds the cap", async () => {
    const got = await refetchPdf("https://h/x.pdf", 1000, async () => resp(PDF, true, { "content-length": "9999" }));
    expect(got).toBeNull();
  });
  test("null on network error", async () => {
    expect(await refetchPdf("https://h/x.pdf", 1000, async () => { throw new Error("net"); })).toBeNull();
  });
});

describe("mirror", () => {
  test("mirrorUrlFor derives sibling om.json", () => {
    expect(mirrorUrlFor("https://h.example.com/dir/deal.pdf")).toBe("https://h.example.com/dir/om.json");
  });
  test("guardedMirrorFetch rejects non-https", async () => {
    expect(await guardedMirrorFetch("http://h/om.json", 1000, async () => resp(PDF))).toBeNull();
  });
  test("guardedMirrorFetch returns body for https", async () => {
    const r = await guardedMirrorFetch("https://h/om.json", 1000, async () => resp(PDF));
    expect(r).toEqual({ https: true, body: PDF });
  });
});
