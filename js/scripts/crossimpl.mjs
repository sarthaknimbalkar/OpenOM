// Cross-implementation harness ([OM-VEC-002]), Track B side.
//   A->B: read Track A's golden PDFs (pikepdf-embedded) with the JS reader and verify.
//   B->A: embed each vector payload with the JS writer and write the PDF to <outDir> for
//         the Python reader (see core/tests/test_crossimpl.py).
// Usage: node js/scripts/crossimpl.mjs <outDir>   (run after `npm run build`)
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { embedPayload } from "../dist/src/embed.js";
import { payloadHash } from "../dist/src/hash.js";
import { readPayloadFromBytes } from "../dist/src/read.js";

const here = dirname(fileURLToPath(import.meta.url));
const vectorsDir = join(here, "..", "..", "spec", "vectors");
const producersDir = join(here, "..", "..", "core", "tests", "fixtures", "producers");
const outDir = process.argv[2];
if (!outDir) {
  console.error("usage: crossimpl.mjs <outDir>");
  process.exit(2);
}
mkdirSync(outDir, { recursive: true });

const manifest = JSON.parse(readFileSync(join(vectorsDir, "manifest.json"), "utf8"));

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

  // B->A: JS writer embeds onto the structurally-rich golden PDF (#131) — a re-embed, so it exercises
  // JS embed into a real AF/EF/XMP/object-stream document, not a fresh blank — for the Python reader.
  const out = await embedPayload(new Uint8Array(golden), payload);
  writeFileSync(join(outDir, `${v.name}.pdf`), out);
}

// B->A producer diversity (#131 + #130): embed onto each committed producer-diverse base so the Python
// reader proves JS embed survives object-stream / linearized / image-only producer structures.
const samplePayload = JSON.parse(
  readFileSync(join(vectorsDir, "payloads", "sample-stnl.json"), "utf8"),
);
for (const producer of ["producer-native", "producer-hybrid", "producer-scanned"]) {
  const base = readFileSync(join(producersDir, `${producer}.pdf`));
  const out = await embedPayload(new Uint8Array(base), samplePayload);
  writeFileSync(join(outDir, `${producer}.pdf`), out);
  console.log(`B->A embedded onto ${producer}`);
}

if (failures) {
  console.error(`${failures} A->B failure(s)`);
  process.exit(1);
}
console.log(
  `A->B all ok; ${manifest.vectors.length} vector + 3 producer B PDFs written to ${outDir}`,
);
