// openOM popup — renders the badge + payload card + publish controls from a DetectResult. The
// render is a PURE function of data (no chrome calls), so it is unit-testable in jsdom; the runtime
// bootstrap (query tab → message the service worker → wire buttons) is guarded at the bottom.

import type { DetectResult } from "../service-worker.js";
import type { Webhook } from "../storage.js";

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
  badge.appendChild(el("strong", "badge-label", result.label));
  badge.appendChild(el("span", "badge-caption", result.caption));
  root.appendChild(badge);

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
if (typeof chrome !== "undefined" && chrome.tabs?.query) {
  void (async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const root = document.getElementById("app");
    if (!tab?.url || !root) return;
    const [{ getWebhook }, result] = await Promise.all([
      import("../storage.js"),
      chrome.runtime.sendMessage({ type: "detect", url: tab.url }) as Promise<DetectResult>,
    ]);
    renderPopup(root, result, await getWebhook());
    // Button wiring (publish/testFire/copy/download) is attached here in the runtime; omitted from
    // the pure render for testability. See publish.ts for the underlying calls.
  })();
}
