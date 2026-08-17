// In-browser decryption of empty-user-password AES-encrypted PDFs (#4) — so author mode can embed into
// permission-encrypted OMs (restrict print/copy, NOT password-protected) instead of refusing them (#107).
// Deterministic, zero inference. Scope: Standard security handler, empty user password, AES only —
// V4/R4 (AESV2, AES-128, per-object keys) and V5/R6 (AESV3, AES-256, file key used directly). Anything
// else (RC4, a real password, unknown /V·/R, any parse/crypto failure) → null; the caller falls back to
// the #107 "use the CLI" message. A wrong key must yield null, never a corrupt PDF: we validate the empty
// user password against /U BEFORE decrypting, and any AES PKCS#7 padding failure aborts to null.
//
// Refs: PDF 32000-1 §7.6 (R2–R4); PDF 32000-2 §7.6.4.3.3–.4 + Adobe "Algorithm 2.B" (R6).
import { cbc } from "@noble/ciphers/aes.js";
import { md5 } from "@noble/hashes/legacy.js";
import { sha256, sha384, sha512 } from "@noble/hashes/sha2.js";
import { concatBytes } from "@noble/hashes/utils.js";

/** 32-byte password-padding string (PDF 32000-1, Algorithm 2). Empty password ⇒ padded password = PAD. */
// prettier-ignore
const PAD = new Uint8Array([
  0x28, 0xbf, 0x4e, 0x5e, 0x4e, 0x75, 0x8a, 0x41, 0x64, 0x00, 0x4e, 0x56, 0xff, 0xfa, 0x01, 0x08,
  0x2e, 0x2e, 0x00, 0xb6, 0xd0, 0x68, 0x3e, 0x80, 0x2f, 0x0c, 0xa9, 0xfe, 0x64, 0x53, 0x69, 0x7a,
]);
const SALT = new Uint8Array([0x73, 0x41, 0x6c, 0x54]); // "sAlT" — AESV2 per-object-key suffix
const EMPTY = new Uint8Array(0);
const ZERO_IV = new Uint8Array(16);

interface EncryptInfo {
  V: number;
  R: number;
  length: number; // key length in BITS
  O: Uint8Array;
  U: Uint8Array;
  UE: Uint8Array;
  P: number; // 32-bit signed
  id0: Uint8Array;
  cfm: string; // "V2" | "AESV2" | "AESV3" | ...
  encryptMetadata: boolean;
  encRef: import("pdf-lib").PDFRef | undefined;
}

/** Decrypt an empty-password AES-encrypted PDF to clean bytes, or null if out of scope / not this case. */
export async function decryptPdf(pdfBytes: Uint8Array): Promise<Uint8Array | null> {
  try {
    const pdfLib = await import("pdf-lib");
    const doc = await pdfLib.PDFDocument.load(pdfBytes, {
      ignoreEncryption: true,
      throwOnInvalidObject: false,
      updateMetadata: false,
    });
    const info = readEncryptInfo(doc.context, pdfLib, pdfBytes);
    if (info === null) return null;
    if (!((info.V === 4 && info.R === 4) || (info.V === 5 && info.R === 6))) return null;
    if (info.cfm !== "AESV2" && info.cfm !== "AESV3") return null;

    let fileKey: Uint8Array | null;
    if (info.R === 4) {
      fileKey = deriveKeyR4(info);
      if (!validateUserPasswordR4(info, fileKey)) return null;
    } else {
      fileKey = deriveKeyR6(info);
      if (fileKey === null) return null;
    }

    // Real OMs pack most objects into compressed object streams (/Type /ObjStm) referenced by an xref
    // stream. pdf-lib DISSOLVES each ObjStm at load — it inflates the container to extract inner objects,
    // but an AES body won't inflate, so the inner objects end up absent / PDFInvalidObject and the
    // container itself is never an enumerable object. An ObjStm's DICT is plaintext (only string values
    // and stream BODIES are encrypted), so we locate containers with a safe raw scan, AES-decrypt each
    // body, and re-run pdf-lib's object-stream parser to register the correct inner objects. Inner objects
    // are never individually encrypted (the container carries their encryption), so we never decrypt them.
    const rawContainers = findObjStmContainers(pdfBytes);
    const containerNums = new Set(rawContainers.map((c) => c.num));

    for (const [ref, obj] of doc.context.enumerateIndirectObjects()) {
      if (info.encRef && ref === info.encRef) continue; // never decrypt the /Encrypt dict
      if (containerNums.has(ref.objectNumber)) continue; // ObjStm container — handled below
      const objKey =
        info.R === 4 ? objectKeyR4(fileKey, ref.objectNumber, ref.generationNumber) : fileKey;
      if (obj instanceof pdfLib.PDFRawStream) {
        const type = typeName(obj.dict, pdfLib);
        if (type === "XRef") continue; // cross-reference streams are never encrypted
        if (type === "Metadata" && !info.encryptMetadata) continue; // unencrypted metadata
        walkDict(obj.dict, objKey, pdfLib); // strings in the stream dict are encrypted too
        const dec = aesCbcDecrypt(objKey, obj.contents);
        obj.dict.set(pdfLib.PDFName.of("Length"), pdfLib.PDFNumber.of(dec.length));
        doc.context.assign(ref, pdfLib.PDFRawStream.of(obj.dict, dec)); // .contents is readonly
      } else {
        decryptObjectTree(obj, objKey, pdfLib);
      }
    }

    for (const c of rawContainers) {
      const objKey = info.R === 4 ? objectKeyR4(fileKey, c.num, c.gen) : fileKey;
      const dec = aesCbcDecrypt(objKey, c.body);
      const d = pdfLib.PDFDict.withContext(doc.context);
      d.set(pdfLib.PDFName.of("N"), pdfLib.PDFNumber.of(c.n));
      d.set(pdfLib.PDFName.of("First"), pdfLib.PDFNumber.of(c.first));
      d.set(pdfLib.PDFName.of("Filter"), pdfLib.PDFName.of("FlateDecode"));
      d.set(pdfLib.PDFName.of("Length"), pdfLib.PDFNumber.of(dec.length));
      const plainStm = pdfLib.PDFRawStream.of(d, dec);
      await pdfLib.PDFObjectStreamParser.forStream(plainStm).parseIntoContext(); // registers inner objects
    }

    delete doc.context.trailerInfo.Encrypt;
    if (info.encRef) doc.context.delete(info.encRef);
    return await doc.save({ useObjectStreams: false });
  } catch {
    return null; // any parse/crypto/validation failure ⇒ fall back to #107
  }
}

type PdfLib = typeof import("pdf-lib");

function typeName(dict: import("pdf-lib").PDFDict, { PDFName }: PdfLib): string | null {
  const t = dict.lookup(PDFName.of("Type"));
  return t instanceof PDFName ? t.decodeText() : null;
}

interface ObjStmContainer {
  num: number;
  gen: number;
  n: number; // /N object count
  first: number; // /First offset
  body: Uint8Array; // raw (encrypted, still flate-wrapped) stream body
}

/**
 * Locate every `/Type /ObjStm` container by scanning the raw bytes. Safe because an ObjStm's dict is
 * NOT encrypted — only string values and stream bodies are — so `/Type /ObjStm`, `/N`, `/First`, and a
 * direct `/Length` appear literally. The encrypted body is sliced by `/Length` (falling back to an
 * `endstream` search). pdf-lib can't hand us these containers (it dissolves them at load), so this is
 * how the ObjStm-decrypt pass reaches them. Latin-1 view: 1 char == 1 byte, so string indices are byte
 * offsets. A stray match inside another object's encrypted body is caught by the pikepdf oracle.
 */
function findObjStmContainers(bytes: Uint8Array): ObjStmContainer[] {
  const S = new TextDecoder("latin1").decode(bytes);
  const out: ObjStmContainer[] = [];
  const objRe = /(\d+)\s+(\d+)\s+obj\b/g;
  let m: RegExpExecArray | null;
  while ((m = objRe.exec(S)) !== null) {
    const hdrEnd = m.index + m[0].length;
    const streamKw = S.indexOf("stream", hdrEnd);
    if (streamKw < 0) continue;
    const endobj = S.indexOf("endobj", hdrEnd);
    if (endobj >= 0 && streamKw > endobj) continue; // no stream in this object
    const dictText = S.slice(hdrEnd, streamKw);
    if (!/\/ObjStm\b/.test(dictText)) continue;
    const nM = /\/N\s+(\d+)/.exec(dictText);
    const fM = /\/First\s+(\d+)/.exec(dictText);
    if (!nM || !fM) continue;

    let bodyStart = streamKw + "stream".length;
    if (S[bodyStart] === "\r") bodyStart++;
    if (S[bodyStart] === "\n") bodyStart++;
    const lenM = /\/Length\s+(\d+)(?!\s+\d+\s+R)/.exec(dictText); // direct /Length only
    let length: number;
    if (lenM) {
      length = Number(lenM[1]);
    } else {
      const es = S.indexOf("endstream", bodyStart);
      if (es < 0) continue;
      let e = es;
      if (S[e - 1] === "\n") e--;
      if (S[e - 1] === "\r") e--;
      length = e - bodyStart;
    }
    out.push({
      num: Number(m[1]),
      gen: Number(m[2]),
      n: Number(nM[1]),
      first: Number(fM[1]),
      body: bytes.subarray(bodyStart, bodyStart + length),
    });
  }
  return out;
}

function asBytes(
  v: import("pdf-lib").PDFObject | undefined,
  { PDFString, PDFHexString }: PdfLib,
): Uint8Array | null {
  return v instanceof PDFString || v instanceof PDFHexString ? v.asBytes() : null;
}

/** Read the /Encrypt dict and /ID[0]; null when there is no Standard-handler /Encrypt. */
function readEncryptInfo(
  ctx: import("pdf-lib").PDFContext,
  pdfLib: PdfLib,
  pdfBytes: Uint8Array,
): EncryptInfo | null {
  const { PDFName, PDFDict, PDFArray, PDFNumber, PDFBool, PDFRef } = pdfLib;
  let enc = ctx.trailerInfo.Encrypt;
  // Pure xref-stream files (common with R6) don't surface /Encrypt in pdf-lib's trailerInfo. The
  // reference is plaintext in the trailer/xref dict — raw-scan for it and look the object up (an
  // /Encrypt dict is always an uncompressed top-level object, so pdf-lib has parsed it).
  if (!enc) {
    const m = /\/Encrypt\s+(\d+)\s+(\d+)\s+R/.exec(new TextDecoder("latin1").decode(pdfBytes));
    if (m) enc = PDFRef.of(Number(m[1]), Number(m[2]));
  }
  const encRef = enc instanceof PDFRef ? enc : undefined;
  const dict = enc instanceof PDFRef ? ctx.lookup(enc) : enc;
  if (!(dict instanceof PDFDict)) return null;
  const filter = dict.lookup(PDFName.of("Filter"));
  if (!(filter instanceof PDFName) || filter.decodeText() !== "Standard") return null;

  const num = (k: string, d = 0): number => {
    const n = dict.lookup(PDFName.of(k));
    return n instanceof PDFNumber ? n.asNumber() : d;
  };
  const O = asBytes(dict.lookup(PDFName.of("O")), pdfLib);
  const U = asBytes(dict.lookup(PDFName.of("U")), pdfLib);
  if (O === null || U === null) return null;
  const UE = asBytes(dict.lookup(PDFName.of("UE")), pdfLib) ?? EMPTY;

  const idArr = ctx.trailerInfo.ID;
  const id0 = idArr instanceof PDFArray ? (asBytes(idArr.get(0), pdfLib) ?? EMPTY) : EMPTY;

  // /CF → /StdCF → /CFM (Name). V4/V5 use crypt filters; absence ⇒ out of scope (null cfm string).
  let cfm = "";
  const cf = dict.lookup(PDFName.of("CF"));
  const stdCf = cf instanceof PDFDict ? cf.lookup(PDFName.of("StdCF")) : undefined;
  const cfmName = stdCf instanceof PDFDict ? stdCf.lookup(PDFName.of("CFM")) : undefined;
  if (cfmName instanceof PDFName) cfm = cfmName.decodeText();

  const emd = dict.lookup(PDFName.of("EncryptMetadata"));
  const encryptMetadata = emd instanceof PDFBool ? emd.asBoolean() : true;

  return {
    V: num("V"),
    R: num("R"),
    length: num("Length", 128),
    O,
    U,
    UE,
    P: num("P") | 0,
    id0,
    cfm,
    encryptMetadata,
    encRef,
  };
}

/** Algorithm 2 (empty user password), R≥3: MD5 with 50 spin rounds. Returns the n-byte file key. */
function deriveKeyR4(info: EncryptInfo): Uint8Array {
  const n = info.length / 8;
  const p = int32LE(info.P);
  const meta =
    info.R >= 4 && !info.encryptMetadata ? new Uint8Array([0xff, 0xff, 0xff, 0xff]) : EMPTY;
  let h = md5(concatBytes(PAD, info.O, p, info.id0, meta));
  for (let i = 0; i < 50; i++) h = md5(h.slice(0, n));
  return h.slice(0, n);
}

/** Algorithm 6/5 (R≥3): recompute /U from the file key and compare its first 16 bytes. RC4-based. */
function validateUserPasswordR4(info: EncryptInfo, fileKey: Uint8Array): boolean {
  let x = rc4(fileKey, md5(concatBytes(PAD, info.id0)));
  for (let i = 1; i <= 19; i++) {
    const k = new Uint8Array(fileKey.length);
    for (let j = 0; j < k.length; j++) k[j] = fileKey[j]! ^ i;
    x = rc4(k, x);
  }
  return constEqual(x.subarray(0, 16), info.U.subarray(0, 16));
}

/** Algorithm 1 per-object key for AESV2: MD5(fileKey ‖ obj(3 LE) ‖ gen(2 LE) ‖ "sAlT"), truncated. */
function objectKeyR4(fileKey: Uint8Array, objNum: number, gen: number): Uint8Array {
  const extra = new Uint8Array([
    objNum & 0xff,
    (objNum >> 8) & 0xff,
    (objNum >> 16) & 0xff,
    gen & 0xff,
    (gen >> 8) & 0xff,
  ]);
  const m = md5(concatBytes(fileKey, extra, SALT));
  return m.slice(0, Math.min(fileKey.length + 5, 16));
}

/** Algorithm 2.A/2.B (R6, empty user password) → 32-byte file key, or null if the password isn't empty. */
function deriveKeyR6(info: EncryptInfo): Uint8Array | null {
  if (info.U.length < 48 || info.UE.length < 32) return null;
  const hash = info.U.subarray(0, 32);
  const validationSalt = info.U.subarray(32, 40);
  const keySalt = info.U.subarray(40, 48);
  if (!constEqual(hash2B(EMPTY, validationSalt, EMPTY), hash)) return null; // user password not empty
  const intermediate = hash2B(EMPTY, keySalt, EMPTY);
  return aesNoPad(intermediate, ZERO_IV, info.UE.subarray(0, 32), false);
}

/** Adobe "Algorithm 2.B" iterative hash (SHA-256/384/512), used for R6 password validation + key wrap. */
function hash2B(password: Uint8Array, salt: Uint8Array, udata: Uint8Array): Uint8Array {
  let K = sha256(concatBytes(password, salt, udata));
  for (let round = 0; ; round++) {
    const block = concatBytes(password, K, udata);
    const K1 = new Uint8Array(block.length * 64);
    for (let i = 0; i < 64; i++) K1.set(block, i * block.length);
    const E = aesNoPad(K.subarray(0, 16), K.subarray(16, 32), K1, true);
    let sum = 0;
    for (let i = 0; i < 16; i++) sum += E[i]!;
    const mod = sum % 3;
    K = mod === 0 ? sha256(E) : mod === 1 ? sha384(E) : sha512(E);
    if (round >= 63 && E[E.length - 1]! <= round - 32) break;
  }
  return K.slice(0, 32);
}

/** AES-CBC with PKCS#7 padding stripped; data = IV(16) ‖ ciphertext. Throws on bad padding (⇒ null). */
function aesCbcDecrypt(key: Uint8Array, data: Uint8Array): Uint8Array {
  if (data.length < 16) return data; // not an AES blob (e.g. a short/empty string) — leave as-is
  return cbc(key, data.subarray(0, 16)).decrypt(data.subarray(16));
}

/** No-padding AES-CBC (whole-block) for the R6 /UE unwrap (decrypt) and Algorithm 2.B inner E (encrypt). */
function aesNoPad(key: Uint8Array, iv: Uint8Array, data: Uint8Array, encrypt: boolean): Uint8Array {
  const c = cbc(key, iv, { disablePadding: true });
  return encrypt ? c.encrypt(data) : c.decrypt(data);
}

/** Decrypt strings in a non-stream indirect object (streams are handled in the main loop via assign). */
function decryptObjectTree(
  obj: import("pdf-lib").PDFObject,
  objKey: Uint8Array,
  pdfLib: PdfLib,
): void {
  const { PDFDict, PDFArray } = pdfLib;
  if (obj instanceof PDFDict) walkDict(obj, objKey, pdfLib);
  else if (obj instanceof PDFArray) walkArray(obj, objKey, pdfLib);
  // A standalone indirect scalar (string/name/number) has no container to rewrite through; our target
  // producers don't emit encrypted top-level indirect strings, so leaving scalars is correct.
}

function decryptString(
  v: import("pdf-lib").PDFObject,
  objKey: Uint8Array,
  pdfLib: PdfLib,
): import("pdf-lib").PDFObject | null {
  const bytes = asBytes(v, pdfLib);
  if (bytes === null) return null;
  const dec = aesCbcDecrypt(objKey, bytes);
  return pdfLib.PDFHexString.of(toHex(dec));
}

function walkDict(dict: import("pdf-lib").PDFDict, objKey: Uint8Array, pdfLib: PdfLib): void {
  const { PDFDict, PDFArray } = pdfLib;
  for (const [name, val] of dict.entries()) {
    const s = decryptString(val, objKey, pdfLib);
    if (s !== null) dict.set(name, s);
    else if (val instanceof PDFDict) walkDict(val, objKey, pdfLib);
    else if (val instanceof PDFArray) walkArray(val, objKey, pdfLib);
  }
}

function walkArray(arr: import("pdf-lib").PDFArray, objKey: Uint8Array, pdfLib: PdfLib): void {
  const { PDFDict, PDFArray } = pdfLib;
  for (let i = 0; i < arr.size(); i++) {
    const val = arr.get(i);
    const s = decryptString(val, objKey, pdfLib);
    if (s !== null) arr.set(i, s);
    else if (val instanceof PDFDict) walkDict(val, objKey, pdfLib);
    else if (val instanceof PDFArray) walkArray(val, objKey, pdfLib);
  }
}

/** RC4 stream cipher — used ONLY for the R4 /U password check (@noble/ciphers omits RC4 by design). */
function rc4(key: Uint8Array, data: Uint8Array): Uint8Array {
  const s = new Uint8Array(256);
  for (let i = 0; i < 256; i++) s[i] = i;
  for (let i = 0, j = 0; i < 256; i++) {
    j = (j + s[i]! + key[i % key.length]!) & 0xff;
    [s[i], s[j]] = [s[j]!, s[i]!];
  }
  const out = new Uint8Array(data.length);
  for (let k = 0, i = 0, j = 0; k < data.length; k++) {
    i = (i + 1) & 0xff;
    j = (j + s[i]!) & 0xff;
    [s[i], s[j]] = [s[j]!, s[i]!];
    out[k] = data[k]! ^ s[(s[i]! + s[j]!) & 0xff]!;
  }
  return out;
}

/** 4 little-endian bytes of a 32-bit signed integer (for /P in the Algorithm 2 MD5 input). */
function int32LE(v: number): Uint8Array {
  const u = v >>> 0;
  return new Uint8Array([u & 0xff, (u >> 8) & 0xff, (u >> 16) & 0xff, (u >> 24) & 0xff]);
}

function toHex(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += b.toString(16).padStart(2, "0");
  return s;
}

/** Constant-time byte-array equality (never leak WHERE a password/hash check diverges). */
function constEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i]! ^ b[i]!;
  return diff === 0;
}
