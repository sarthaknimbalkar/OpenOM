// @vitest-environment jsdom
import { describe, expect, test } from "vitest";
import { renderOptions } from "../../src/options.js";

describe("renderOptions (#70)", () => {
  test("renders profile, webhook, and the Q8 setting toggles from the stored values", () => {
    const root = document.createElement("div");
    renderOptions(root, {
      profile: { broker: "Jane", brokerage: "Acme", license: "CA-1" },
      webhook: { url: "https://h/x", secret: "shh" },
      settings: { proactiveDetection: false, linkBadgingDomains: ["buildout.com"] },
    });
    expect((root.querySelector(".o-broker") as HTMLInputElement).value).toBe("Jane");
    expect((root.querySelector(".o-wh-url") as HTMLInputElement).value).toBe("https://h/x");
    expect((root.querySelector(".o-wh-secret") as HTMLInputElement).type).toBe("password");
    expect((root.querySelector(".o-linkbadging-domains") as HTMLTextAreaElement).value).toBe("buildout.com");
    expect((root.querySelector(".o-proactive") as HTMLInputElement).checked).toBe(false);
    expect(root.querySelector("#save")).not.toBeNull();
  });
});
