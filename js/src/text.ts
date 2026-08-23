// Deterministic per-page text extraction via pdf.js - the ONLY input author-mode inference reads
// ([OM-DoD-007] M5b-2). Worker-AGNOSTIC: it never references `chrome` or configures a worker, so it
// is a clean /js module reused unchanged in Node (tests) and the browser panel (which owns worker
// setup). No inference here; pdf.js is already a /js dependency.

import { loadPdfjs } from "./pdfjs.js";

export interface PageText {
  readonly page: number;
  readonly text: string;
}

/**
 * Point pdf.js at its worker (a plain URL string - this stays worker-agnostic and never touches
 * `chrome`; the browser caller supplies the extension URL). Sets it on the SAME pdf.js module instance
 * `extractPageText` imports, so a browser page (which requires a real worker) can run extraction.
 */
export async function setPdfWorkerSrc(src: string): Promise<void> {
  const pdfjs = await loadPdfjs();
  pdfjs.GlobalWorkerOptions.workerSrc = src;
}

export interface PageTextResult {
  /** Extracted pages (1..min(totalPages, maxPages)). */
  pages: PageText[];
  /** The document's TRUE page count - so the caller can tell it read only a prefix (never silent). */
  totalPages: number;
}

/** Extract text for pages 1..min(totalPages, maxPages), reporting the true page count for truncation. */
export async function extractPageText(bytes: Uint8Array, maxPages = 40): Promise<PageTextResult> {
  const pdfjs = await loadPdfjs();
  const pdf = await pdfjs.getDocument({ data: bytes.slice(), verbosity: 0 }).promise;
  try {
    const totalPages = pdf.numPages;
    const last = Math.min(totalPages, maxPages);
    const pages: PageText[] = [];
    for (let p = 1; p <= last; p++) {
      const content = await (await pdf.getPage(p)).getTextContent();
      pages.push({
        page: p,
        text: layoutText(content.items as Array<{ str?: string; transform?: number[] }>),
      });
    }
    return { pages, totalPages };
  } finally {
    await pdf.destroy();
  }
}

/**
 * Reconstruct rough page layout from pdf.js text items ([#103]): group items into lines by their
 * y-position, order lines top→bottom and items left→right. A flat space-join destroys tables (rent
 * schedules, financial summaries) - the fields extraction most needs - so we keep line + column
 * structure the model can read. Deterministic; item positions come from the text transform.
 */
function layoutText(items: Array<{ str?: string; transform?: number[] }>): string {
  const rows: { y: number; cells: { x: number; str: string }[] }[] = [];
  for (const it of items) {
    if (typeof it.str !== "string" || it.str === "") continue;
    const t = it.transform;
    const x = Array.isArray(t) && typeof t[4] === "number" ? t[4] : 0;
    const y = Array.isArray(t) && typeof t[5] === "number" ? t[5] : 0;
    let row = rows.find((r) => Math.abs(r.y - y) < 2); // items within 2 units share a line
    if (!row) {
      row = { y, cells: [] };
      rows.push(row);
    }
    row.cells.push({ x, str: it.str });
  }
  rows.sort((a, b) => b.y - a.y); // PDF origin is bottom-left: higher y = higher on the page
  return rows
    .map((r) =>
      r.cells
        .sort((a, b) => a.x - b.x)
        .map((c) => c.str)
        .join(" "),
    )
    .join("\n");
}
