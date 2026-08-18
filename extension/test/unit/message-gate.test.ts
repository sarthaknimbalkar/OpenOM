import { describe, expect, test } from "vitest";
import { accepts, isContentScript } from "../../src/message-gate.js";

const RID = "abcdefghijklmnopabcdefghijklmnop";

describe("#127 SW message-origin gate", () => {
  test("rejects a message from another extension / a web page (wrong id)", () => {
    expect(
      accepts(
        { id: "other", tab: {}, url: "https://evil.test/" },
        "detect",
        RID,
      ),
    ).toBe(false);
    expect(
      accepts({ id: undefined, url: "https://evil.test/" }, "detect", RID),
    ).toBe(false);
  });

  test("the real toolbar popup (no tab) is accepted for any verb", () => {
    const sender = { id: RID, url: `chrome-extension://${RID}/popup.html` };
    expect(isContentScript(sender)).toBe(false);
    expect(accepts(sender, "detect", RID)).toBe(true);
    expect(accepts(sender, "author:fetch", RID)).toBe(true);
  });

  // The regression: an extension page opened IN A TAB has sender.tab set but a chrome-extension URL.
  test("popup deep-link / side panel (extension page in a tab) is accepted for any verb", () => {
    const sender = {
      id: RID,
      tab: { id: 7 },
      url: `chrome-extension://${RID}/popup.html?url=x`,
    };
    expect(isContentScript(sender)).toBe(false);
    expect(accepts(sender, "detect", RID)).toBe(true);
    expect(accepts(sender, "author:fetch", RID)).toBe(true);
  });

  test("a true content script (tab + http page URL) is confined to the badge verbs", () => {
    const cs = {
      id: RID,
      tab: { id: 3 },
      url: "https://listing.example.com/deal",
    };
    expect(isContentScript(cs)).toBe(true);
    expect(accepts(cs, "linkbadge:enabled", RID)).toBe(true);
    expect(accepts(cs, "linkbadge:verify", RID)).toBe(true);
    expect(accepts(cs, "detect", RID)).toBe(false);
    expect(accepts(cs, "author:fetch", RID)).toBe(false);
    expect(accepts(cs, "embed", RID)).toBe(false);
  });

  test("a tab sender with no/opaque URL is treated as a content script (restrictive default)", () => {
    expect(isContentScript({ id: RID, tab: {}, url: undefined })).toBe(true);
  });
});
