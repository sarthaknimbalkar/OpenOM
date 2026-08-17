// FAST producer-diversity pass over the OMs/ corpus (#20/#22, Q3): embed a payload into every OM via
// the extension's /js embedPayload, read it back, and structure-diff (pages/bookmarks/links) — all in
// Node via pdf-lib, NO rendering, so it scales to thousands of files. Groups outcomes by PDF producer
// so we see which real-world producers the load→save embed survives. Local only. Needs `npm --prefix
// js run build`. Run: `node js/scripts/real-om-fast.mjs`.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { PDFArray, PDFDict, PDFDocument, PDFName } from "pdf-lib";
import { embedPayload } from "../dist/src/embed.js";
import { readPayloadFromBytes } from "../dist/src/read.js";

const repo = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const OMS = join(repo, "OMs");
const payload = JSON.parse(readFileSync(join(repo, "spec", "samples", "valid-stnl.json"), "utf8"));

function walk(dir) {
  const out = [];
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (n.toLowerCase().endsWith(".pdf")) out.push(p);
  }
  return out;
}

async function structure(doc) {
  let bookmarks = 0;
  const outlines = doc.catalog.lookup(PDFName.of("Outlines"));
  if (outlines instanceof PDFDict) {
    let node = outlines.lookup(PDFName.of("First"));
    while (node instanceof PDFDict) {
      bookmarks++;
      node = node.lookup(PDFName.of("Next"));
    }
  }
  let links = 0;
  for (const pg of doc.getPages()) {
    const annots = pg.node.lookup(PDFName.of("Annots"));
    if (annots instanceof PDFArray)
      for (let i = 0; i < annots.size(); i++) {
        const a = doc.context.lookup(annots.get(i));
        if (a instanceof PDFDict && a.lookup(PDFName.of("Subtype")) === PDFName.of("Link")) links++;
      }
  }
  return { pages: doc.getPageCount(), bookmarks, links };
}

const files = walk(OMS);
const byProducer = new Map(); // producer -> {ok, structChange, embedFail, readFail}
const bump = (prod, key) => {
  const r = byProducer.get(prod) ?? { ok: 0, structChange: 0, embedFail: 0, readFail: 0 };
  r[key]++;
  byProducer.set(prod, r);
};
let ok = 0;
const failSamples = [];

for (const src of files) {
  let producer = "?";
  try {
    const bytes = new Uint8Array(readFileSync(src));
    const before = await PDFDocument.load(bytes, {
      throwOnInvalidObject: false,
      updateMetadata: false,
    });
    producer = (before.getProducer() ?? "?").slice(0, 40);
    const sBefore = await structure(before);
    let embedded;
    try {
      embedded = await embedPayload(bytes, payload);
    } catch (e) {
      bump(producer, "embedFail");
      failSamples.push(
        `embedFail ${String(e.message).slice(0, 40)} :: ${src.slice(OMS.length + 1)}`,
      );
      continue;
    }
    const read = await readPayloadFromBytes(embedded);
    if (read.state !== "present" || read.verification.hashValid !== true) {
      bump(producer, "readFail");
      continue;
    }
    const sAfter = await structure(
      await PDFDocument.load(embedded, { throwOnInvalidObject: false }),
    );
    if (
      sAfter.pages !== sBefore.pages ||
      sAfter.bookmarks !== sBefore.bookmarks ||
      sAfter.links !== sBefore.links
    ) {
      bump(producer, "structChange");
      failSamples.push(
        `struct ${sBefore.pages}/${sBefore.bookmarks}/${sBefore.links}→${sAfter.pages}/${sAfter.bookmarks}/${sAfter.links} :: ${src.slice(OMS.length + 1)}`,
      );
    } else {
      bump(producer, "ok");
      ok++;
    }
  } catch (e) {
    bump(producer, "embedFail");
    failSamples.push(`load ${String(e.message).slice(0, 40)} :: ${src.slice(OMS.length + 1)}`);
  }
}

console.log("producer".padEnd(42), "ok  chg  embFail  rdFail");
for (const [prod, r] of [...byProducer.entries()].sort(
  (a, b) => b[1].ok + b[1].structChange - (a[1].ok + a[1].structChange),
)) {
  if (r.structChange || r.embedFail || r.readFail || r.ok)
    console.log(
      prod.padEnd(42),
      `${r.ok}`.padStart(4),
      `${r.structChange}`.padStart(4),
      `${r.embedFail}`.padStart(7),
      `${r.readFail}`.padStart(6),
    );
}
console.log(
  `\n${ok}/${files.length} embed + round-trip + structure preserved (Node structural pass; no render)`,
);
console.log("--- first failures ---");
for (const s of failSamples.slice(0, 25)) console.log(s);
console.log(`(+${Math.max(0, failSamples.length - 25)} more)`);
