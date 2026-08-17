// The review panel — the human assertion gate (§7a, process/review-contract.md). A PURE DOM render
// (no chrome, no clock, no /js) so it is jsdom-testable; panel.ts recomputes validation on each edit
// and passes the report in. It renders the four contract sections and gates the Assert button on the
// schema-error count ALONE — never on extraction confidence, never pre-checked ([OM-EXTP-003]).
import type { ValidationReport } from "openom-js";
import { type Draft, fieldsWithoutEvidence, leaves, omissions } from "./draft.js";

export interface RepriceDiff {
  added: string[];
  changed: [string, unknown, unknown][];
  removed: string[];
  supersedes: string;
}

export interface ReviewView {
  report: ValidationReport;
  diff: RepriceDiff | null;
}

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

/** Diff of a reprice: added / changed (old→new) / removed leaves, plus the prior hash to supersede. */
export function repriceDiff(
  prior: Record<string, unknown>,
  next: Record<string, unknown>,
  priorHash: string,
): RepriceDiff {
  const p = new Map(leaves(prior));
  const n = new Map(leaves(next));
  const added = [...n.keys()].filter((k) => !p.has(k));
  const removed = [...p.keys()].filter((k) => !n.has(k));
  const changed: [string, unknown, unknown][] = [...n.keys()]
    .filter((k) => p.has(k) && p.get(k) !== n.get(k))
    .map((k) => [k, p.get(k), n.get(k)]);
  return { added, changed, removed, supersedes: priorHash };
}

/** Render the review contract; sets `#assert.disabled` iff there are schema errors. */
export function renderReview(root: HTMLElement, draft: Draft, view: ReviewView): void {
  root.replaceChildren();
  const { report, diff } = view;
  const flagged = new Set(fieldsWithoutEvidence(draft));

  // 1 — per field: value + evidence + source tag; flag values lacking citable evidence.
  const fields = el("section", "fields");
  fields.appendChild(el("h2", undefined, "Fields"));
  for (const [path, value] of leaves(draft.payload)) {
    const row = el("div", "review-field");
    row.appendChild(el("span", "field-path", path));
    row.appendChild(el("span", "field-value", String(value)));
    const ev = draft.evidence[path];
    if (ev && (ev.page !== undefined || ev.quote)) {
      row.appendChild(el("span", "field-evidence", `p.${ev.page ?? "?"} "${ev.quote ?? ""}"`));
    }
    if (flagged.has(path)) row.appendChild(el("span", "field-flag", "no evidence — please cite"));
    fields.appendChild(row);
  }
  root.appendChild(fields);

  // 2 — omissions (schema-known but unset). SCHEMA_LEAF_PATHS lives here so the panel can confirm them.
  const missing = omissions(draft, SCHEMA_LEAF_PATHS);
  if (missing.length) {
    const sec = el("section", "omissions");
    sec.appendChild(el("h2", undefined, "Omitted (confirm or supply)"));
    for (const m of missing) sec.appendChild(el("div", "omission", m));
    root.appendChild(sec);
  }

  // 3 — residual warnings (never block).
  if (report.warnings.length) {
    const sec = el("section", "warnings");
    sec.appendChild(el("h2", undefined, "Residual warnings"));
    for (const w of report.warnings) {
      sec.appendChild(el("div", "residual-warning", `${w.code} — ${w.message}`));
    }
    root.appendChild(sec);
  }

  // Schema errors block the assertion; show them so the human can fix values.
  if (report.errors.length) {
    const sec = el("section", "errors");
    sec.appendChild(el("h2", undefined, "Errors (must fix before asserting)"));
    for (const e of report.errors) sec.appendChild(el("div", "schema-error", `${e.code} ${e.path} — ${e.message}`));
    root.appendChild(sec);
  }

  // 4 — reprice diff (re-embed only).
  if (diff) {
    const sec = el("section", "reprice-diff");
    sec.appendChild(el("h2", undefined, "Reprice — you are approving a change"));
    for (const [p, o, nv] of diff.changed) sec.appendChild(el("div", "diff-changed", `${p}: ${String(o)} → ${String(nv)}`));
    for (const a of diff.added) sec.appendChild(el("div", "diff-added", `+ ${a}`));
    for (const r of diff.removed) sec.appendChild(el("div", "diff-removed", `− ${r}`));
    sec.appendChild(el("div", "diff-supersedes", `supersedes ${diff.supersedes}`));
    root.appendChild(sec);
  }

  // Assert gate — disabled iff schema errors. Never pre-checked, never enabled by anything else.
  const assert = el("button", "assert", "Assert & Embed") as HTMLButtonElement;
  assert.id = "assert";
  assert.disabled = report.errors.length > 0;
  root.appendChild(assert);
}

/** Required/expected leaf paths surfaced as omissions when unset (§E; kept minimal, non-blocking). */
const SCHEMA_LEAF_PATHS = [
  "/assertedBy/broker",
  "/assertedBy/brokerage",
  "/assertedBy/license",
  "/deal/askingPrice",
  "/deal/noi",
  "/deal/capRate",
];
