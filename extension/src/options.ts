// openOM settings page (#70) - the single home for the device-local broker profile, the publish
// webhook, and the §15 Q8 opt-ins. Everything is chrome.storage.local ONLY (never sync). The render
// is a pure function of the stored values; the runtime bootstrap loads + saves. Uses the shared
// design system (popup.css). No inference.
import { getProfile, setProfile, type BrokerProfile } from "./author/profile.js";
import { getWebhook, setWebhook, getSettings, setSettings, type Settings, type Webhook } from "./storage.js";

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

function field(labelText: string, input: HTMLElement): HTMLElement {
  const label = el("label");
  label.append(`${labelText} `, input);
  return label;
}
function textInput(cls: string, value: string, password = false): HTMLInputElement {
  const i = el("input", cls) as HTMLInputElement;
  i.type = password ? "password" : "text";
  i.value = value;
  i.setAttribute("aria-label", cls.replace(/^o-/, "").replace(/-/g, " "));
  return i;
}
function toggle(cls: string, checked: boolean): HTMLInputElement {
  const i = el("input", cls) as HTMLInputElement;
  i.type = "checkbox";
  i.checked = checked;
  return i;
}

export interface OptionsView {
  profile: BrokerProfile;
  webhook: Webhook;
  settings: Settings;
}

/** Render the settings form (pure). Controls expose stable classes the bootstrap reads on save. */
export function renderOptions(root: HTMLElement, v: OptionsView): void {
  root.replaceChildren();
  root.appendChild(el("h1", "title", "openOM settings"));

  const prof = el("section", "profile");
  prof.appendChild(el("h2", undefined, "Reviewing broker"));
  prof.append(
    field("Broker", textInput("o-broker", v.profile.broker)),
    field("Brokerage", textInput("o-brokerage", v.profile.brokerage ?? "")),
    field("License", textInput("o-license", v.profile.license ?? "")),
  );
  root.appendChild(prof);

  const hook = el("section", "webhook");
  hook.appendChild(el("h2", undefined, "Publish webhook"));
  hook.append(
    field("Receiver URL", textInput("o-wh-url", v.webhook.url)),
    field("Signing secret", textInput("o-wh-secret", v.webhook.secret, true)),
  );
  root.appendChild(hook);

  const set = el("section", "settings");
  set.appendChild(el("h2", undefined, "Detection (privacy)"));
  const domains = el("textarea", "o-linkbadging-domains") as HTMLTextAreaElement;
  domains.value = v.settings.linkBadgingDomains.join("\n");
  domains.setAttribute("aria-label", "Link-badging domains, one per line");
  set.append(
    field("Proactively detect on navigation (off = check when you open the popup)", toggle("o-proactive", v.settings.proactiveDetection)),
    field("Badge openOM links on these domains (one per line)", domains),
  );
  root.appendChild(set);

  const save = el("button", "o-save", "Save settings") as HTMLButtonElement;
  save.id = "save";
  root.appendChild(save);
  const status = el("p", "status");
  status.setAttribute("aria-live", "polite");
  root.appendChild(status);
}

// ---- runtime bootstrap (guarded so unit tests can import renderOptions without chrome) ----
if (typeof chrome !== "undefined" && chrome.storage?.local) {
  void (async () => {
    const root = document.getElementById("options");
    if (!root) return;
    renderOptions(root, {
      profile: (await getProfile()) ?? { broker: "", brokerage: "", license: "" },
      webhook: (await getWebhook()) ?? { url: "", secret: "" },
      settings: await getSettings(),
    });
    const val = (cls: string) => (root.querySelector(`.${cls}`) as HTMLInputElement | null)?.value ?? "";
    const checked = (cls: string) => (root.querySelector(`.${cls}`) as HTMLInputElement | null)?.checked ?? false;
    root.querySelector("#save")?.addEventListener("click", async () => {
      await setProfile({ broker: val("o-broker"), brokerage: val("o-brokerage"), license: val("o-license") });
      await setWebhook({ url: val("o-wh-url"), secret: val("o-wh-secret") });
      const domainList = val("o-linkbadging-domains")
        .split("\n")
        .map((d) => d.trim())
        .filter((d) => d.length > 0);
      await setSettings({
        proactiveDetection: checked("o-proactive"),
        linkBadgingDomains: [...new Set(domainList)],
      });
      const status = root.querySelector(".status");
      if (status) status.textContent = "Saved.";
    });
  })();
}
