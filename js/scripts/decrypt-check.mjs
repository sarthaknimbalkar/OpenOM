// Dev-only correctness oracle for decryptPdf (#4). NOT in CI — the corpus (OMs/) is confidential and
// gitignored. Runs decryptPdf over every encrypted OM and hands the results to decrypt_oracle.py, which
// renders each against pikepdf's own decryption (the reference) and asserts they are render-identical.
//
// Usage (from repo root):  npm --prefix js run build  &&  node js/scripts/decrypt-check.mjs [corpusDir]
// Then:                    .venv/Scripts/python.exe js/scripts/decrypt_oracle.py
import { readFileSync, writeFileSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { decryptPdf } from "../dist/src/decrypt.js";

const here = fileURLToPath(new URL(".", import.meta.url));
const corpus = resolve(process.argv[2] ?? join(here, "..", "..", "OMs"));
const outDir = join(here, "..", "..", ".decrypt-oracle");
rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

function* pdfs(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* pdfs(p);
    else if (e.name.toLowerCase().endsWith(".pdf")) yield p;
  }
}

const manifest = [];
let i = 0;
for (const path of pdfs(corpus)) {
  const bytes = new Uint8Array(readFileSync(path));
  let out = null;
  try {
    out = await decryptPdf(bytes);
  } catch {
    out = null;
  }
  const rec = { src: path, decrypted: null };
  if (out) {
    const outPath = join(outDir, `dec-${i}.pdf`);
    writeFileSync(outPath, out);
    rec.decrypted = outPath;
  }
  manifest.push(rec);
  i++;
  if (i % 100 === 0) console.error(`  processed ${i}…`);
}
writeFileSync(join(outDir, "manifest.json"), JSON.stringify(manifest, null, 0));
const decrypted = manifest.filter((m) => m.decrypted).length;
console.error(`scanned ${manifest.length} PDFs; decryptPdf produced output for ${decrypted}.`);
console.error(`manifest → ${join(outDir, "manifest.json")}`);
