// openOM popup - renders the badge + payload card + publish controls from a DetectResult. The
// render is a PURE function of data (no chrome calls), so it is unit-testable in jsdom; the runtime
// bootstrap (query tab → message the service worker → wire buttons) is guarded at the bottom.

import { wordmark } from "../wordmark.js";
import { envelopeText, publishWithRetry, testFire } from "../publish.js";
import type { DetectResult } from "../service-worker.js";
import { getWebhook, setWebhook, type Webhook } from "../storage.js";
import { summarizeDeal } from "openom-js";

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

function renderCard(result: DetectResult): HTMLElement {
  const card = el("section", "card");
  const p = result.payload ?? {};
  const lease = (p.lease as Record<string, unknown>) ?? {};
  // [M3] one typed, formatted, currency-aware view - includes the assertion metadata (noiType, as-of,
  // asserted date/brokerage) that makes this an ASSERTION, not a bare number.
  const s = summarizeDeal(p);

  const noiText =
    s.noiText && (s.noiType || s.noiAsOfDate)
      ? `${s.noiText} (${[s.noiType, s.noiAsOfDate ? `as of ${s.noiAsOfDate}` : null].filter(Boolean).join(", ")})`
      : s.noiText;
  const rows: [string, string | null][] = [
    ["Property", s.propertyType],
    ["Address", s.address],
    ["Asking price", s.askingPriceText],
    ["Cap rate", s.capRateText],
    ["NOI", noiText],
    ["$/SF", s.pricePerSFText],
    ["Tenant", s.tenant],
    ["Lease type", s.leaseType],
    ["Lease term", s.termMonths ? `${s.termMonths} mo` : null],
    ["Asserted by", [s.assertedByBroker, s.assertedByBrokerage].filter(Boolean).join(", ") || null],
    ["Asserted", s.assertedDate],
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
  root.appendChild(wordmark());

  const badge = el("div", `badge badge-${result.state}`);
  badge.setAttribute("role", "status"); // #71 - announce the trust state to assistive tech
  badge.setAttribute("aria-label", `${result.label}. ${result.caption}`);
  badge.appendChild(el("strong", "badge-label", result.label));
  badge.appendChild(el("span", "badge-caption", result.caption));
  root.appendChild(badge);

  // Author-mode entry point (#76): open the side panel to embed a payload. Class-only (no
  // data-action) so it stays outside the publish-controls set.
  root.appendChild(el("button", "open-author", "Embed a payload…"));

  // Per-site link-badging opt-in (#69). Wired in the runtime bootstrap (needs the tab's domain).
  const lb = el("label", "lb");
  const lbToggle = el("input", "lb-toggle") as HTMLInputElement;
  lbToggle.type = "checkbox";
  lb.append(lbToggle, " Badge openOM links on this site");
  root.appendChild(lb);

  if (result.stale) {
    const s = el(
      "p",
      "stale",
      "A newer version of this deal has been posted by the source. This copy is genuine but out of date.",
    );
    s.title = "OMW-W051 (superseded)"; // raw code available on hover, not in the sentence
    root.appendChild(s);
  }
  if (result.findings.length) {
    const warn = el("ul", "findings");
    // Show the plain-English message; keep the raw code on hover (title), not in the sentence itself.
    const notices = result.notices ?? [];
    for (const code of result.findings) {
      const n = notices.find((x) => x.code === code);
      const li = el("li", undefined, n ? n.message : code);
      li.title = code;
      warn.appendChild(li);
    }
    root.appendChild(el("h3", undefined, "Things to double-check"));
    root.appendChild(warn);
  }

  // Card only when there's a trustworthy payload to show (not on absent/hash-mismatch).
  if (result.state === "integrity-ok" || result.state === "origin-verified") {
    root.appendChild(renderCard(result));

    // [M3] This is a developer integration (a signed §Y webhook to a connected CRM/portal), NOT
    // buyer distribution. Frame it as such and tuck it behind an "Advanced" disclosure so a broker
    // isn't misled into thinking "Publish" sends the deal to buyers. To share with a buyer, a broker
    // rehosts the embedded PDF (or uses the openom.app verified link, when hosted).
    const publish = el("details", "publish") as HTMLDetailsElement;
    const sum = el("summary", undefined, "Advanced: send to a connected system (webhook)");
    publish.appendChild(sum);
    publish.appendChild(
      el(
        "p",
        "publish-hint",
        "Sends an HMAC change-notification to your own CRM/portal endpoint. This is not how buyers receive the OM - for that, rehost the embedded PDF.",
      ),
    );
    const target = el("input", "wh-target") as HTMLInputElement;
    target.placeholder = "https://your-crm-endpoint…";
    target.value = webhook?.url ?? "";
    const secret = el("input", "wh-secret") as HTMLInputElement;
    secret.type = "password";
    secret.placeholder = "signing secret";
    secret.value = webhook?.secret ?? "";
    publish.append(target, secret);
    for (const [label, action] of [
      ["Test fire", "test-fire"],
      ["Send", "publish"],
      ["Copy", "copy"],
      ["Download", "download"],
    ] as const) {
      const b = el("button", undefined, label) as HTMLButtonElement;
      b.dataset.action = action;
      publish.appendChild(b);
    }
    root.appendChild(publish);
  }

  // Settings footer - where the broker profile lives (set your name/brokerage/license once, and
  // it's filled in on every OM). Discoverable from the popup, not buried. Wired in the bootstrap.
  const settings = el("button", "open-settings", "Settings - save your broker profile");
  root.appendChild(settings);
}

// ---- runtime bootstrap (guarded so jsdom tests can import renderPopup without chrome) ----
if (typeof chrome !== "undefined" && chrome.runtime?.sendMessage) {
  void (async () => {
    const root = document.getElementById("app");
    if (!root) return;
    try {
      // Target URL: a ?url= deep-link (used by the harness + as a shareable check link), else the
      // active tab. The pipeline runs identically for both - only the source of the URL differs.
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
        root.textContent = `Couldn't read this PDF: ${result.error}`;
        return;
      }
      renderPopup(root, result, await getWebhook());
      wireButtons(root, result);
      wireOpenAuthor(root);
      wireSettings(root);
      wireLinkBadge(root, result);
    } catch (e) {
      root.textContent = `Couldn't read this PDF: ${(e as Error).message}`;
    }
  })();
}

/** Attach publish/test-fire/copy/download behavior to the rendered controls (runtime only). */
function wireButtons(root: HTMLElement, result: DetectResult): void {
  const target = () => (root.querySelector("input.wh-target") as HTMLInputElement | null)?.value ?? "";
  const secret = () => (root.querySelector("input.wh-secret") as HTMLInputElement | null)?.value ?? "";
  const status = document.createElement("p");
  status.className = "status";
  status.setAttribute("aria-live", "polite"); // #71 - announce publish/test-fire outcomes
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
    status.textContent = "Copied the signed record";
  });
  root.querySelector('[data-action="download"]')?.addEventListener("click", () => {
    const blob = new Blob([envelopeText({ ...args(), event: "om.payload.published" })], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "openom-envelope.json";
    a.click();
    status.textContent = "Downloaded the signed record";
  });
}

/** Open the author-mode side panel to embed a payload (#76). Requires a user gesture - the click. */
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

/** Open the options page (where the broker profile is set) from the popup Settings link. */
function wireSettings(root: HTMLElement): void {
  root.querySelector(".open-settings")?.addEventListener("click", () => {
    chrome.runtime.openOptionsPage();
    window.close();
  });
}

/** Per-site link-badging toggle (#69): seed from the SW's allowlist, flip the current domain on change. */
function wireLinkBadge(root: HTMLElement, result: DetectResult): void {
  const cb = root.querySelector(".lb-toggle") as HTMLInputElement | null;
  if (!cb) return;
  let hostname: string;
  try {
    hostname = new URL(result.sourceUrl).hostname;
  } catch {
    cb.disabled = true;
    return;
  }
  void chrome.runtime.sendMessage({ type: "linkbadge:enabled", hostname }).then((r: { enabled?: boolean }) => {
    cb.checked = !!r?.enabled;
  });
  cb.addEventListener("change", () => {
    void chrome.runtime
      .sendMessage({ type: "linkbadge:toggle", hostname })
      .then((r: { enabled?: boolean }) => {
        cb.checked = !!r?.enabled;
      });
  });
}
