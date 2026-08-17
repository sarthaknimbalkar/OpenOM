// The review panel — the human assertion gate (§7a, process/review-contract.md). A PURE DOM render
// (no chrome, no clock, no /js) so it is jsdom-testable; panel.ts recomputes validation on each edit
// and passes the report in. It renders the four contract sections and gates the Assert button on the
// schema-error count ALONE — never on extraction confidence, never pre-checked ([OM-EXTP-003]).
import type { ValidationReport } from "openom-js";
import { type Draft, leaves, omissions } from "./draft.js";
import schema from "../../../spec/om-0.1.schema.json";
import { schemaExpectedPaths } from "./schema-paths.js";

export interface RepriceDiff {
  added: string[];
  changed: [string, unknown, unknown][];
  removed: string[];
  supersedes: string;
}

export interface DerivedView {
  report: ValidationReport;
  diff: RepriceDiff | null;
  /** The exact payload finalize() would embed — shown read-only so the human approves it (#95). */
  finalized: Record<string, unknown>;
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

/**
 * Render the DERIVED review output — everything computed from the draft (validation, omissions,
 * warnings, reprice diff, the finalized-payload preview, and the Assert gate). It contains NO text
 * inputs (those live in the form), so re-rendering it on every edit never disturbs focus. Assert is
 * disabled iff there are schema errors — never pre-checked, never enabled by anything else.
 */
export function renderDerived(container: HTMLElement, draft: Draft, view: DerivedView): void {
  container.replaceChildren();
  const { report, diff, finalized } = view;

  // Omissions (schema-known but unset) — from the whole field map ([#92]).
  const missing = omissions(draft, SCHEMA_LEAF_PATHS);
  if (missing.length) {
    const sec = el("section", "omissions");
    sec.appendChild(el("h2", undefined, "Omitted (confirm or supply)"));
    for (const m of missing) sec.appendChild(el("div", "omission", m));
    container.appendChild(sec);
  }

  // 3 — residual warnings (never block).
  if (report.warnings.length) {
    const sec = el("section", "warnings");
    sec.appendChild(el("h2", undefined, "Residual warnings"));
    for (const w of report.warnings) {
      sec.appendChild(el("div", "residual-warning", `${w.code} — ${w.message}`));
    }
    container.appendChild(sec);
  }

  // Schema errors block the assertion; show them so the human can fix values.
  if (report.errors.length) {
    const sec = el("section", "errors");
    sec.appendChild(el("h2", undefined, "Errors (must fix before asserting)"));
    for (const e of report.errors) sec.appendChild(el("div", "schema-error", `${e.code} ${e.path} — ${e.message}`));
    container.appendChild(sec);
  }

  // 4 — reprice diff (re-embed only).
  if (diff) {
    const sec = el("section", "reprice-diff");
    sec.appendChild(el("h2", undefined, "Reprice — you are approving a change"));
    for (const [p, o, nv] of diff.changed) sec.appendChild(el("div", "diff-changed", `${p}: ${String(o)} → ${String(nv)}`));
    for (const a of diff.added) sec.appendChild(el("div", "diff-added", `+ ${a}`));
    for (const r of diff.removed) sec.appendChild(el("div", "diff-removed", `− ${r}`));
    sec.appendChild(el("div", "diff-supersedes", `supersedes ${diff.supersedes}`));
    container.appendChild(sec);
  }

  // #95 — the exact payload that will be embedded (stamped assertedBy/assertedDate/@context/meta),
  // read-only, so the human approves what actually gets written before asserting.
  const preview = el("section", "finalized-preview");
  preview.appendChild(el("h2", undefined, "Will be embedded"));
  const pre = el("pre", "finalized-json");
  pre.textContent = stableStringify(finalized);
  preview.appendChild(pre);
  container.appendChild(preview);

  // Assert gate — disabled iff schema errors. Never pre-checked, never enabled by anything else.
  const assert = el("button", "assert", "Assert & Embed") as HTMLButtonElement;
  assert.id = "assert";
  assert.disabled = report.errors.length > 0;
  container.appendChild(assert);
}

/** Deterministic 2-space JSON for the preview (keys sorted so the view is stable across edits). */
function stableStringify(value: unknown): string {
  return JSON.stringify(value, (_k, v) =>
    v && typeof v === "object" && !Array.isArray(v)
      ? Object.fromEntries(Object.entries(v as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b)))
      : v,
  2);
}

/** Expected leaf paths surfaced as omissions when unset — derived from the schema/field map ([#92]). */
const SCHEMA_LEAF_PATHS = schemaExpectedPaths(schema as { properties?: Record<string, unknown> });
