// Generate the author-mode extraction fixture: a PDF WITH a real text layer, so the M5b-2 extraction
// gate exercises the scanned-vs-text path (#91) and pdf.js text extraction. The other author fixtures
// are blank/embedded (built by extension/test/harness/build_fixtures.py); this one needs pdf-lib's
// drawText, which resolves here in /js. Regenerate:
//   node js/scripts/gen_author_text_fixture.mjs extension/test/harness/fixtures/author/text.pdf
import { PDFDocument, StandardFonts } from "pdf-lib";
import { writeFileSync } from "node:fs";

const out = process.argv[2] ?? "../extension/test/harness/fixtures/author/text.pdf";
const doc = await PDFDocument.create();
const font = await doc.embedFont(StandardFonts.Helvetica);
const p = doc.addPage([612, 792]);
p.drawText("1000 Example Rd - Offering Memorandum", { x: 50, y: 740, size: 14, font });
p.drawText("Cap Rate: 5.75%", { x: 50, y: 700, size: 12, font });
p.drawText("NOI: 431250", { x: 50, y: 680, size: 12, font });
p.drawText("Asking Price: 7500000", { x: 50, y: 660, size: 12, font });
p.drawText("Tenant: Example Retailer LLC", { x: 50, y: 640, size: 12, font });
writeFileSync(out, await doc.save());
console.log("wrote", out);
