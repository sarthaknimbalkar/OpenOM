import { describe, expect, test } from "vitest";
import { parsePayload, DEFAULT_MAX_PAYLOAD_BYTES } from "../src/parse.js";

/**
 * §J [OM-SEC-002] decompression/size guard. A payload larger than the cap is
 * rejected before parsing so a hostile input cannot exhaust memory.
 */
describe("[OM-SEC-002] payload size cap → OM-IO-BOMB", () => {
  test("exposes a documented default cap", () => {
    expect(DEFAULT_MAX_PAYLOAD_BYTES).toBe(5 * 1024 * 1024);
  });

  test("rejects input over the default cap (bytes)", () => {
    const oversized = new Uint8Array(DEFAULT_MAX_PAYLOAD_BYTES + 1);
    expect(() => parsePayload(oversized)).toThrowError(
      expect.objectContaining({ code: "OM-IO-BOMB" }),
    );
  });

  test("honours a caller-supplied maxBytes", () => {
    const text = `{"a":"${"x".repeat(100)}"}`;
    expect(() => parsePayload(text, { maxBytes: 16 })).toThrowError(
      expect.objectContaining({ code: "OM-IO-BOMB" }),
    );
  });

  test("accepts input at exactly the cap", () => {
    // 16-byte body: {"a":"xxxxxxxx"} is 16 bytes.
    const text = '{"a":"xxxxxxxx"}';
    expect(new TextEncoder().encode(text).length).toBe(16);
    expect(parsePayload(text, { maxBytes: 16 })).toEqual({ a: "xxxxxxxx" });
  });
});

/**
 * §J read-side bomb guard: a flate-compressed om.json that inflates past the cap is rejected
 * BEFORE full materialization (Node bounded inflate), matching the Python core (Task 5).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import zlib from "node:zlib";
import { PDFDocument, PDFName, PDFArray, PDFDict, PDFRawStream } from "pdf-lib";
import { embedPayload } from "../src/embed.js";
import { readPayloadFromBytes } from "../src/read.js";

const specDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "spec");
const validStnl = JSON.parse(
  readFileSync(join(specDir, "samples", "valid-stnl.json"), "utf8"),
) as Record<string, unknown>;

describe("[OM-SEC-002] read-side decompression bomb → OM-IO-BOMB", () => {
  test("a flate-bomb om.json stream is rejected on read (bounded inflate)", async () => {
    const doc = await PDFDocument.create();
    doc.addPage([612, 792]);
    const embedded = await embedPayload(await doc.save(), validStnl);

    const loaded = await PDFDocument.load(embedded);
    const af = loaded.catalog.lookup(PDFName.of("AF")) as PDFArray;
    const filespec = loaded.context.lookup(af.get(0)) as PDFDict;
    const ef = filespec.lookup(PDFName.of("EF")) as PDFDict;
    const stream = loaded.context.lookup(ef.get(PDFName.of("F"))) as PDFRawStream;
    // 6 MiB inflated, tiny compressed — the classic bomb.
    const bomb = zlib.deflateSync(Buffer.alloc(6 * 1024 * 1024, 0x41));
    (stream as unknown as { contents: Uint8Array }).contents = new Uint8Array(bomb);
    const bombPdf = await loaded.save();

    await expect(readPayloadFromBytes(bombPdf)).rejects.toThrowError(
      expect.objectContaining({ code: "OM-IO-BOMB" }),
    );
  });
});
