// Package the built extension into a Chrome-Web-Store-ready zip ([#104]). Builds dist, then zips the
// CONTENTS of dist/ (manifest.json at the zip root, as the store requires) into
// openom-extension-<version>.zip. A local human step — not CI.
//
// Self-contained ZIP writer (no dependency): entry names use FORWARD SLASHES on every platform — the
// Windows `Compress-Archive`/.NET path wrote backslash separators, which the Chrome Web Store and Chrome
// mishandle (resources not found). Deterministic: sorted entries + fixed DOS timestamps, so the same
// dist/ always produces a byte-identical zip.
import { execSync } from "node:child_process";
import { deflateRawSync } from "node:zlib";
import {
  existsSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(
  readFileSync(join(root, "public", "manifest.json"), "utf8"),
);
const zipName = `openom-extension-${manifest.version}.zip`;
const zipPath = join(root, zipName);
const dist = join(root, "dist");

console.log("building…");
execSync("node build.mjs", { cwd: root, stdio: "inherit" });
if (existsSync(zipPath)) rmSync(zipPath);

/** All files under dir, as { name (forward-slash, dist-relative), data } — sorted for reproducibility. */
function collect(dir) {
  const out = [];
  const walk = (d) => {
    for (const entry of readdirSync(d).sort()) {
      const p = join(d, entry);
      if (statSync(p).isDirectory()) walk(p);
      else
        out.push({
          name: relative(dist, p).split("\\").join("/"),
          data: readFileSync(p),
        });
    }
  };
  walk(dir);
  return out.sort((a, b) => (a.name < b.name ? -1 : 1));
}

const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return (buf) => {
    let c = 0xffffffff;
    for (let i = 0; i < buf.length; i++) c = t[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
})();

/** Minimal ZIP (deflate, method 8) with forward-slash names and fixed timestamps. */
function buildZip(files) {
  const locals = [];
  const central = [];
  let offset = 0;
  const DOS_TIME = 0; // fixed → reproducible
  const DOS_DATE = 0x21; // 1980-01-01
  for (const f of files) {
    const nameBuf = Buffer.from(f.name, "utf8");
    const crc = CRC(f.data);
    const comp = deflateRawSync(f.data);
    const lh = Buffer.alloc(30);
    lh.writeUInt32LE(0x04034b50, 0);
    lh.writeUInt16LE(20, 4); // version needed
    lh.writeUInt16LE(0, 6); // flags
    lh.writeUInt16LE(8, 8); // method: deflate
    lh.writeUInt16LE(DOS_TIME, 10);
    lh.writeUInt16LE(DOS_DATE, 12);
    lh.writeUInt32LE(crc, 14);
    lh.writeUInt32LE(comp.length, 18);
    lh.writeUInt32LE(f.data.length, 22);
    lh.writeUInt16LE(nameBuf.length, 26);
    lh.writeUInt16LE(0, 28); // extra len
    locals.push(lh, nameBuf, comp);

    const ch = Buffer.alloc(46);
    ch.writeUInt32LE(0x02014b50, 0);
    ch.writeUInt16LE(20, 4); // version made by
    ch.writeUInt16LE(20, 6); // version needed
    ch.writeUInt16LE(0, 8);
    ch.writeUInt16LE(8, 10);
    ch.writeUInt16LE(DOS_TIME, 12);
    ch.writeUInt16LE(DOS_DATE, 14);
    ch.writeUInt32LE(crc, 16);
    ch.writeUInt32LE(comp.length, 20);
    ch.writeUInt32LE(f.data.length, 24);
    ch.writeUInt16LE(nameBuf.length, 28);
    ch.writeUInt32LE(offset, 42);
    central.push(ch, nameBuf);
    offset += 30 + nameBuf.length + comp.length;
  }
  const localBlob = Buffer.concat(locals);
  const centralBlob = Buffer.concat(central);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(files.length, 8);
  eocd.writeUInt16LE(files.length, 10);
  eocd.writeUInt32LE(centralBlob.length, 12);
  eocd.writeUInt32LE(localBlob.length, 16);
  return Buffer.concat([localBlob, centralBlob, eocd]);
}

console.log(`zipping dist/ → ${zipName}`);
const files = collect(dist);
writeFileSync(zipPath, buildZip(files));
console.log(`packaged ${files.length} files: ${zipPath}`);
console.log(
  "Upload this zip to the Chrome Web Store, or load dist/ unpacked at chrome://extensions.",
);
