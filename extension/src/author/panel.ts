// openOM author-mode side panel — capture → review → assert → embed → hand back. Deterministic;
// ZERO inference in B1 (on-device extraction arrives in M5b-2). The panel document is the ONLY place
// that reads the clock (assertedDate) and touches chrome.* panel APIs; the workflow logic lives in
// the pure, testable modules (capture / draft / review-panel / assert). This file is the bootstrap;
// Task 5 wires the full capture→review→assert flow. For now it renders the initial capture screen.

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

/** Render the entry screen: capture the current tab's PDF, or pick a local file. */
export function renderCaptureScreen(root: HTMLElement): void {
  root.replaceChildren();
  root.appendChild(el("h1", "title", "openOM — embed a payload"));
  root.appendChild(
    el("p", "hint", "Capture an offering memorandum, review its data, assert, and embed."),
  );

  const useTab = el("button", "capture-tab", "Use current tab's PDF") as HTMLButtonElement;
  useTab.dataset.action = "capture-tab";
  const file = el("input", "capture-file") as HTMLInputElement;
  file.type = "file";
  file.accept = "application/pdf,.pdf";
  root.append(useTab, el("span", "sep", "or"), file);
}

// ---- runtime bootstrap (guarded so jsdom/unit imports don't require chrome) ----
if (typeof chrome !== "undefined" && chrome.runtime?.id) {
  const root = document.getElementById("author");
  if (root) renderCaptureScreen(root);
}
