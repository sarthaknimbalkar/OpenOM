// LOCAL real-OM non-destructive check ([OM-DoD-001], #20/#22): embed a payload into every OM in the
// confidential OMs/ corpus via the EXTENSION's embed path (/js embedPayload), read it back, and diff
// structure + rendered pixels against the original. Not CI (the corpus is confidential + gitignored).
//
// Prereqs: `npm --prefix js run build` (this imports the compiled dist) and the repo venv with
// pikepdf/pymupdf/numpy. Run: `node js/scripts/real-om-check.mjs`.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { embedPayload } from "../dist/src/embed.js";
import { readPayloadFromBytes } from "../dist/src/read.js";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..");
const OMS = join(repo, "OMs");
const PY = join(repo, ".venv", "Scripts", "python.exe");
const ANALYZE = join(here, "om_analyze.py");
const payload = JSON.parse(readFileSync(join(repo, "spec", "samples", "valid-stnl.json"), "utf8"));

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (name.toLowerCase().endsWith(".pdf")) out.push(p);
  }
  return out;
}

const files = walk(OMS);
const tmp = mkdtempSync(join(tmpdir(), "om-check-"));
let pass = 0;
let visualPerfect = 0;
const rows = [];

for (const src of files) {
  const rel = src.slice(OMS.length + 1);
  try {
    const bytes = new Uint8Array(readFileSync(src));
    const embedded = await embedPayload(bytes, payload);
    const read = await readPayloadFromBytes(embedded);
    if (read.state !== "present" || read.verification.hashValid !== true) {
      rows.push({ rel, status: `read-back ${read.state}/${read.verification.hashValid}` });
      continue;
    }
    const out = join(tmp, "e.pdf");
    writeFileSync(out, embedded);
    const a = JSON.parse(execFileSync(PY, [ANALYZE, src, out], { encoding: "utf8" }));
    const structOk =
      a.pages[0] === a.pages[1] && a.bookmarks[0] === a.bookmarks[1] && a.links[0] === a.links[1];
    const perfect = a.max_pixel_diff === 0;
    if (structOk && a.min_ssim >= 0.9999) pass++;
    if (perfect) visualPerfect++;
    rows.push({
      rel,
      status: `pg ${a.pages[0]}→${a.pages[1]} bk ${a.bookmarks[0]}→${a.bookmarks[1]} lk ${a.links[0]}→${a.links[1]} | ssim ${a.min_ssim} maxdiff ${a.max_pixel_diff} ${structOk && a.min_ssim >= 0.9999 ? "OK" : "‼"}`,
    });
  } catch (e) {
    rows.push({ rel, status: `ERROR ${String(e.message).slice(0, 80)}` });
  }
}
rmSync(tmp, { recursive: true, force: true });

for (const r of rows) console.log(`${r.status.padEnd(64)} ${r.rel}`);
console.log(
  `\n${pass}/${files.length} preserve structure + SSIM≥0.9999 · ${visualPerfect}/${files.length} pixel-identical render`,
);
