// Brand wordmark: "open" + a highlighted "OM", matching the openom.app header. Rendered as the page
// <h1> so it doubles as the accessible page heading. Styling lives in popup.css (.wordmark).
export function wordmark(sub?: string): HTMLElement {
  const h = document.createElement("h1");
  h.className = "wordmark";
  h.append("open");
  const om = document.createElement("span");
  om.className = "om";
  om.textContent = "OM";
  h.append(om);
  if (sub) {
    const s = document.createElement("span");
    s.className = "sub";
    s.textContent = sub;
    h.append(s);
  }
  return h;
}
