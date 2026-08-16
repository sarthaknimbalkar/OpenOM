#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Generate /spec/vectors/expected/*.json, manifest.json, and golden PDFs (spec §B).

- expected/*.json: integrity hash + base64 of the exact JCS bytes (byte-match oracle).
- pdfs/*.pdf + *.expected.json: deterministic pikepdf-embedded golden PDFs so the Track B
  (pdf.js/pdf-lib) reader can run the cross-implementation round-trip [OM-VEC-002] against
  Track A output.

Deterministic: fixed assertedDate + deterministic_id, so re-running produces byte-identical
files (no git churn). Run after any payload change:  python core/scripts/gen_vectors.py
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pikepdf

from openom_core.canonical import canonicalize, hash_bytes, payload_hash
from openom_core.embed import embed

ROOT = Path(__file__).resolve().parents[2]
VECTORS = ROOT / "spec" / "vectors"
PAYLOADS = VECTORS / "payloads"
EXPECTED = VECTORS / "expected"
PDFS = VECTORS / "pdfs"
FIXED_DATE = "2026-08-15"

DIMENSIONS: dict[str, dict[str, list[str]]] = {
    "cafe": {"role": ["producer", "consumer"], "level": ["L1"], "pathology": []},
    "unicode": {"role": ["producer", "consumer"], "level": ["L1"], "pathology": []},
    "numbers": {"role": ["producer", "consumer"], "level": ["L1"], "pathology": []},
    "sample-stnl": {
        "role": ["producer", "consumer", "validator"],
        "level": ["L1"],
        "pathology": [],
    },
}


def _write_json(path: Path, obj: object) -> None:
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _deterministic_base() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    buf = io.BytesIO()
    pdf.save(buf, deterministic_id=True)
    return buf.getvalue()


def main() -> None:
    EXPECTED.mkdir(parents=True, exist_ok=True)
    PDFS.mkdir(parents=True, exist_ok=True)
    base = _deterministic_base()
    vectors = []
    for payload_path in sorted(PAYLOADS.glob("*.json")):
        name = payload_path.stem
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        jcs = canonicalize(payload)
        dims = DIMENSIONS.get(
            name, {"role": ["producer", "consumer"], "level": ["L1"], "pathology": []}
        )
        _write_json(
            EXPECTED / f"{name}.json",
            {
                "payload": f"payloads/{name}.json",
                "jcs_sha256": hash_bytes(jcs),
                "jcs_b64": base64.b64encode(jcs).decode("ascii"),
            },
        )
        # Golden PDF (Track-A pikepdf embed) + sidecar for the cross-impl gate.
        (PDFS / f"{name}.pdf").write_bytes(embed(base, payload, asserted_date=FIXED_DATE))
        _write_json(
            PDFS / f"{name}.expected.json",
            {
                "payload": f"payloads/{name}.json",
                "payloadHash": payload_hash(payload),
                "assertedDate": FIXED_DATE,
                "xmp": {
                    "specName": "openOM",
                    "specVersion": str(payload.get("specVersion", "0.1")),
                    "payloadFilename": "om.json",
                    "payloadHash": payload_hash(payload),
                    "assertedDate": FIXED_DATE,
                },
            },
        )
        vectors.append(
            {
                "name": name,
                "payload": f"payloads/{name}.json",
                "expected": f"expected/{name}.json",
                "pdf": f"pdfs/{name}.pdf",
                "dimensions": dims,
            }
        )
    _write_json(
        VECTORS / "manifest.json",
        {"specVersion": "0.1", "suite": "openom-vectors", "vectors": vectors},
    )
    print(f"wrote {len(vectors)} vectors + {len(vectors)} golden PDFs + manifest.json")


if __name__ == "__main__":
    main()
