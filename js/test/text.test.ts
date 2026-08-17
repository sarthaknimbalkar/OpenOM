import { describe, expect, test } from "vitest";
import { PDFDocument, StandardFonts } from "pdf-lib";
import { extractPageText } from "../src/text.js";

async function twoPagePdf(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const p1 = doc.addPage([612, 792]);
  p1.drawText("Cap Rate 5.75 percent", { x: 50, y: 700, size: 12, font });
  const p2 = doc.addPage([612, 792]);
  p2.drawText("NOI 100000 dollars", { x: 50, y: 700, size: 12, font });
  return doc.save();
}

describe("extractPageText — worker-agnostic pdf.js page text", () => {
  test("returns per-page text", async () => {
    const pages = await extractPageText(await twoPagePdf());
    expect(pages).toHaveLength(2);
    expect(pages[0]).toMatchObject({ page: 1 });
    expect(pages[0]?.text).toContain("Cap Rate 5.75");
    expect(pages[1]?.text).toContain("NOI 100000");
  });

  test("respects the page cap", async () => {
    const pages = await extractPageText(await twoPagePdf(), 1);
    expect(pages).toHaveLength(1);
    expect(pages[0]?.page).toBe(1);
  });

  test("preserves line structure top-to-bottom (#103)", async () => {
    const doc = await PDFDocument.create();
    const font = await doc.embedFont(StandardFonts.Helvetica);
    const page = doc.addPage([612, 792]);
    page.drawText("Year 1 Rent 100000", { x: 50, y: 700, size: 12, font });
    page.drawText("Year 2 Rent 110000", { x: 50, y: 650, size: 12, font });
    const [p] = await extractPageText(await doc.save());
    const lines = p!.text.split("\n");
    expect(lines[0]).toContain("Year 1"); // higher on the page comes first
    expect(lines.some((l) => l.includes("Year 2"))).toBe(true);
    expect(p!.text.indexOf("Year 1")).toBeLessThan(p!.text.indexOf("Year 2"));
  });
});
