#!/usr/bin/env python
"""Dev-only oracle half for #4 — verify decryptPdf output against pikepdf's own decryption.

Reads .decrypt-oracle/manifest.json (produced by decrypt-check.mjs). For each source PDF that pikepdf
reports as encrypted-with-empty-password:
  - classify by /V,/R and crypt-filter (AES vs RC4);
  - if decryptPdf produced output, render page 1 of OUR output vs pikepdf's reference decryption and
    assert render-identity (max pixel diff == 0);
  - if decryptPdf returned null, that is only acceptable for out-of-scope files (RC4 / non-empty
    password); an in-scope AES file returning null is a FAIL.

Prints a PASS/FAIL/SKIP split by R4/R6. Any FAIL is a decrypt bug — stop and debug that file.
Corpus is confidential; this script and its output are never committed.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pikepdf
import pymupdf

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST = ROOT / ".decrypt-oracle" / "manifest.json"


def cfm(pdf: pikepdf.Pdf) -> str:
    try:
        cf = pdf.trailer["/Encrypt"].get("/CF")
        return str(cf["/StdCF"]["/CFM"]) if cf else ""
    except Exception:
        return ""


def render_page0(data: bytes) -> np.ndarray:
    doc = pymupdf.open(stream=data, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=100)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    doc.close()
    return arr


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    stats = {"R4": {"pass": 0, "fail": 0}, "R6": {"pass": 0, "fail": 0}, "skip": 0, "plain": 0}
    fails: list[str] = []

    for rec in manifest:
        src = Path(rec["src"])
        try:
            ref = pikepdf.open(src)  # opens iff empty user password
        except pikepdf.PasswordError:
            stats["skip"] += 1  # real password → out of scope (decryptPdf must have returned null)
            if rec["decrypted"]:
                fails.append(f"{src.name}: decrypted a password-protected PDF (should be null)")
            continue
        except Exception:
            stats["plain"] += 1
            continue

        if not ref.is_encrypted:
            stats["plain"] += 1
            ref.close()
            continue

        v, r = int(ref.encryption.V), int(ref.encryption.R)
        is_aes = "AES" in cfm(ref)
        in_scope = is_aes and ((v == 4 and r == 4) or (v == 5 and r == 6))
        band = "R6" if r == 6 else "R4"

        if not rec["decrypted"]:
            if in_scope:
                fails.append(f"{src.name}: in-scope AES (V{v}/R{r}) returned null")
                stats[band]["fail"] += 1
            else:
                stats["skip"] += 1  # RC4 / other → correctly null
            ref.close()
            continue

        # decryptPdf produced output — compare render vs pikepdf's reference decryption.
        buf = io.BytesIO()
        ref.save(buf)  # pikepdf writes an unencrypted reference
        ref.close()
        try:
            ours = render_page0(Path(rec["decrypted"]).read_bytes())
            theirs = render_page0(buf.getvalue())
            ok = ours.shape == theirs.shape and int(np.abs(ours.astype(int) - theirs.astype(int)).max()) == 0
        except Exception as e:
            ok = False
            fails.append(f"{src.name}: render error {e}")
        if ok:
            stats[band]["pass"] += 1
        else:
            stats[band]["fail"] += 1
            fails.append(f"{src.name}: render mismatch (V{v}/R{r})")

    print(json.dumps(stats, indent=2))
    print(f"\nR4: {stats['R4']['pass']} pass / {stats['R4']['fail']} fail")
    print(f"R6: {stats['R6']['pass']} pass / {stats['R6']['fail']} fail")
    print(f"skipped (out-of-scope/non-empty-pw): {stats['skip']}   non-encrypted: {stats['plain']}")
    if fails:
        print(f"\n{len(fails)} FAILURES:")
        for f in fails[:40]:
            print("  -", f)
    else:
        print("\nALL IN-SCOPE ENCRYPTED OMs DECRYPTED RENDER-IDENTICAL TO PIKEPDF [OK]")


if __name__ == "__main__":
    main()
