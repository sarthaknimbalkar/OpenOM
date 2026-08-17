import { beforeEach, describe, expect, test, vi } from "vitest";
import { getDraft, setDraft, clearDraft } from "../../src/author/draft-store.js";
import { newDraft, setField } from "../../src/author/draft.js";

beforeEach(() => {
  const store: Record<string, unknown> = {};
  (globalThis as unknown as { chrome: unknown }).chrome = {
    storage: {
      local: {
        get: async (k: string) => ({ [k]: store[k] }),
        set: async (o: Record<string, unknown>) => Object.assign(store, o),
        remove: async (k: string) => delete store[k],
      },
      sync: { set: vi.fn(), get: vi.fn() },
    },
  };
});

describe("draft-store (#94) — device-local draft persistence", () => {
  test("round-trips a draft by source id, then clears", async () => {
    const d = setField(newDraft(), "/deal/capRate", 0.0575);
    await setDraft("sha256:abc", d);
    expect((await getDraft("sha256:abc"))?.payload).toEqual(d.payload);
    await clearDraft("sha256:abc");
    expect(await getDraft("sha256:abc")).toBeNull();
  });

  test("drafts are isolated per source id", async () => {
    await setDraft("id1", setField(newDraft(), "/deal/noi", 1));
    expect(await getDraft("id2")).toBeNull();
  });
});
