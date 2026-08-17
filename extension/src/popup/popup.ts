// openOM popup — renders the badge + payload card + publish controls from a DetectResult. The
// render is a PURE function of data (no chrome calls), so it is unit-testable in jsdom; the runtime
// bootstrap (query tab → message the service worker → wire buttons) is guarded at the bottom.

import { envelopeText, publishWithRetry, testFire } from "../publish.js";
import type { DetectResult } from "../service-worker.js";
import { getWebhook, setWebhook, type Webhook } from "../storage.js";

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

function renderCard(result: DetectResult): HTMLElement {
  const card = el("section", "card");
  const p = result.payload ?? {};
  const deal = (p.deal as Record<string, unknown>) ?? {};
  const lease = (p.lease as Record<string, unknown>) ?? {};
  const by = (p.assertedBy as Record<string, unknown>) ?? {};
  const addr = ((p.property as Record<string, unknown>)?.address as Record<string, unknown>) ?? {};

  const rows: [string, unknown][] = [
    ["Broker", by.broker],
    ["Address", [addr.streetAddress, addr.addressLocality, addr.addressRegion].filter(Boolean).join(", ")],
    ["Asking price", deal.askingPrice],
    ["Cap rate", deal.capRate],
    ["NOI", deal.noi],
    ["Tenant", lease.tenantEntity],
    ["Lease type", lease.leaseTypeAsserted],
  ];
  const dl = el("dl", "fields");
  for (const [k, v] of rows) {
    if (v === undefined || v === "" || v === null) continue;
    dl.appendChild(el("dt", undefined, k));
    dl.appendChild(el("dd", undefined, String(v)));
  }
  card.appendChild(dl);

  const schedule = (lease.rentSchedule as Record<string, unknown>[]) ?? [];
  if (schedule.length) {
    const list = el("ul", "schedule");
    for (const period of schedule) {
      const src = String(period.source ?? "extracted");
      list.appendChild(
        el("li", undefined, `${period.periodStart}–${period.periodEnd}: ${period.annualRent} [${src}]`),
      );
    }
    card.appendChild(el("h3", undefined, "Rent schedule"));
    card.appendChild(list);
  }
  return card;
}

export function renderPopup(root: HTMLElement, result: DetectResult, webhook: Webhook | null): void {
  root.replaceChildren();

  const badge = el("div", `badge badge-${result.state}`);
  badge.setAttribute("role", "status"); // #71 — announce the trust state to assistive tech
  badge.setAttribute("aria-label", `${result.label}. ${result.caption}`);
  badge.appendChild(el("strong", "badge-label", result.label));
  badge.appendChild(el("span", "badge-caption", result.caption));
  root.appendChild(badge);

  // Author-mode entry point (#76): open the side panel to embed a payload. Class-only (no
  // data-action) so it stays outside the publish-controls set.
  root.appendChild(el("button", "open-author", "Embed a payload…"));

  if (result.stale) {
    root.appendChild(el("p", "stale", "Stale: a newer payload exists at the origin (OMW-W051). This copy is unaltered but superseded."));
  }
  if (result.findings.length) {
    const warn = el("ul", "findings");
    for (const code of result.findings) warn.appendChild(el("li", undefined, code));
    root.appendChild(el("h3", undefined, "Notices"));
    root.appendChild(warn);
  }

  // Card only when there's a trustworthy payload to show (not on absent/hash-mismatch).
  if (result.state === "integrity-ok" || result.state === "origin-verified") {
    root.appendChild(renderCard(result));

    const publish = el("section", "publish");
    publish.appendChild(el("h3", undefined, "Publish"));
    const target = el("input", "wh-target") as HTMLInputElement;
    target.placeholder = "https://your-webhook…";
    target.value = webhook?.url ?? "";
    const secret = el("input", "wh-secret") as HTMLInputElement;
    secret.type = "password";
    secret.placeholder = "signing secret";
    secret.value = webhook?.secret ?? "";
    publish.append(target, secret);
    for (const [label, action] of [
      ["Test fire", "test-fire"],
      ["Publish", "publish"],
      ["Copy", "copy"],
      ["Download", "download"],
    ] as const) {
      const b = el("button", undefined, label) as HTMLButtonElement;
      b.dataset.action = action;
      publish.appendChild(b);
    }
    root.appendChild(publish);
  }
}

// ---- runtime bootstrap (guarded so jsdom tests can import renderPopup without chrome) ----
if (typeof chrome !== "undefined" && chrome.runtime?.sendMessage) {
  void (async () => {
    const root = document.getElementById("app");
    if (!root) return;
    try {
      // Target URL: a ?url= deep-link (used by the harness + as a shareable check link), else the
      // active tab. The pipeline runs identically for both — only the source of the URL differs.
      const override = new URLSearchParams(location.search).get("url");
      let url = override ?? undefined;
      let tabId: number | undefined;
      if (chrome.tabs?.query) {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        tabId = tab?.id; // so the SW can set a PER-TAB badge (#83)
        if (!url) url = tab?.url;
      }
      if (!url) return;
      const result = (await chrome.runtime.sendMessage({ type: "detect", url, tabId })) as
        | DetectResult
        | { error: string };
      if ("error" in result) {
        root.textContent = `openOM error: ${result.error}`;
        return;
      }
      renderPopup(root, result, await getWebhook());
      wireButtons(root, result);
      wireOpenAuthor(root);
    } catch (e) {
      root.textContent = `openOM error: ${(e as Error).message}`;
    }
  })();
}

/** Attach publish/test-fire/copy/download behavior to the rendered controls (runtime only). */
function wireButtons(root: HTMLElement, result: DetectResult): void {
  const target = () => (root.querySelector("input.wh-target") as HTMLInputElement | null)?.value ?? "";
  const secret = () => (root.querySelector("input.wh-secret") as HTMLInputElement | null)?.value ?? "";
  const status = document.createElement("p");
  status.className = "status";
  status.setAttribute("aria-live", "polite"); // #71 — announce publish/test-fire outcomes
  root.appendChild(status);

  const args = () => ({
    sourceUrl: result.sourceUrl,
    payload: result.payload ?? {},
    payloadHash: result.payloadHash ?? "",
    verification: result.verification,
    target: target(),
    secret: secret(),
    now: new Date(),
    id: crypto.randomUUID(),
    deliveryId: crypto.randomUUID(),
  });

  root.querySelector('[data-action="test-fire"]')?.addEventListener("click", async () => {
    try {
      await setWebhook({ url: target(), secret: secret() });
      const r = await testFire(args());
      status.textContent = `Test fire → ${r.status}`;
    } catch (e) {
      status.textContent = `Blocked: ${(e as Error).message}`;
    }
  });
  root.querySelector('[data-action="publish"]')?.addEventListener("click", async () => {
    try {
      await setWebhook({ url: target(), secret: secret() });
      const r = await publishWithRetry({ ...args(), event: "om.payload.published" });
      status.textContent = `Published → ${r.status} (${r.attempts} attempt${r.attempts > 1 ? "s" : ""})`;
    } catch (e) {
      status.textContent = `Blocked: ${(e as Error).message}`;
    }
  });
  root.querySelector('[data-action="copy"]')?.addEventListener("click", () => {
    void navigator.clipboard?.writeText(envelopeText({ ...args(), event: "om.payload.published" }));
    status.textContent = "Copied envelope";
  });
  root.querySelector('[data-action="download"]')?.addEventListener("click", () => {
    const blob = new Blob([envelopeText({ ...args(), event: "om.payload.published" })], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "openom-envelope.json";
    a.click();
    status.textContent = "Downloaded envelope";
  });
}

/** Open the author-mode side panel to embed a payload (#76). Requires a user gesture — the click. */
function wireOpenAuthor(root: HTMLElement): void {
  root.querySelector(".open-author")?.addEventListener("click", () => {
    void (async () => {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.id !== undefined) await chrome.sidePanel.open({ tabId: tab.id });
      else if (tab?.windowId !== undefined) await chrome.sidePanel.open({ windowId: tab.windowId });
      window.close();
    })();
  });
}
