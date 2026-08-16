// Cross-implementation harness ([OM-VEC-002]), Track B side.
//   A->B: read Track A's golden PDFs (pikepdf-embedded) with the JS reader and verify.
//   B->A: embed each vector payload with the JS writer and write the PDF to <outDir> for
//         the Python reader (see core/tests/test_crossimpl.py).
// Usage: node js/scripts/crossimpl.mjs <outDir>   (run after `npm run build`)
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { PDFDocument } from "pdf-lib";
import { embedPayload } from "../dist/src/embed.js";
import { payloadHash } from "../dist/src/hash.js";
import { readPayloadFromBytes } from "../dist/src/read.js";

const here = dirname(fileURLToPath(import.meta.url));
const vectorsDir = join(here, "..", "..", "spec", "vectors");
const outDir = process.argv[2];
if (!outDir) {
  console.error("usage: crossimpl.mjs <outDir>");
  process.exit(2);
}
mkdirSync(outDir, { recursive: true });

const manifest = JSON.parse(readFileSync(join(vectorsDir, "manifest.json"), "utf8"));

async function blankPdf() {
  const doc = await PDFDocument.create();
  doc.addPage([612, 792]);
  return doc.save();
}

let failures = 0;
for (const v of manifest.vectors) {
  const payload = JSON.parse(readFileSync(join(vectorsDir, v.payload), "utf8"));
  const expected = payloadHash(payload);

  // A->B: JS reader over Track A's golden PDF.
  const golden = readFileSync(join(vectorsDir, v.pdf));
  const r = await readPayloadFromBytes(new Uint8Array(golden));
  if (r.state !== "present" || r.verification.hashValid !== true || r.payloadHash !== expected) {
    console.error(
      `A->B FAIL ${v.name}: state=${r.state} hashValid=${r.verification.hashValid} ` +
        `hash=${r.payloadHash} want=${expected}`,
    );
    failures++;
  } else {
    console.log(`A->B ok   ${v.name}`);
  }

  // B->A: JS writer -> PDF for the Python reader.
  const out = await embedPayload(await blankPdf(), payload);
  writeFileSync(join(outDir, `${v.name}.pdf`), out);
}

if (failures) {
  console.error(`${failures} A->B failure(s)`);
  process.exit(1);
}
console.log(`A->B all ok; ${manifest.vectors.length} B PDFs written to ${outDir}`);
