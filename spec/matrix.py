# SPDX-License-Identifier: MIT
"""Conformance fixture matrix (§B.3) + the M1 exit tool `python -m spec.matrix --assert-full`.

The M1 gate ([OM-DoD-001](e)) refuses to exit until every (producer × pathology) cell is filled.
Two axes:

- **Pathologies** (synthesizable, committed, CI-checkable): messy rent schedule, CMYK/SMask
  images, flattened scan, empty payload, hash mismatch. Each has a deterministic generator here.
- **Producers** (real provenance, from the confidential corpus under ``OMs/``): InDesign,
  Word, Buildout, scanned - detected from each PDF's ``/Producer`` metadata. These are local;
  ``OMs/`` is git-ignored, so CI checks only the pathology axis.

Modes:
    python -m spec.matrix               # report the matrix
    python -m spec.matrix --assert-synthetic  # pathology axis only (CI); exit 1 on a gap
    python -m spec.matrix --assert-full       # both axes (local, needs OMs/); exit 1 on a gap
"""

from __future__ import annotations

import argparse
import io
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pikepdf
import pymupdf
from openom_core.embed import embed
from openom_core.inspect import inspect as _inspect
from openom_core.xmp import write_marker

ROOT = Path(__file__).resolve().parents[1]
OMS = ROOT / "OMs"

PRODUCERS = ("indesign", "word", "buildout", "scanned")
PATHOLOGIES = ("messy-schedule", "cmyk-smask", "flattened-scan", "empty-payload", "hash-mismatch")


def _base_pdf() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    buf = io.BytesIO()
    pdf.save(buf, deterministic_id=True)
    return buf.getvalue()


def _sample() -> dict[str, Any]:
    return json.loads((ROOT / "spec" / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


# --- pathology generators (deterministic; each returns a fixture artifact's bytes) ------

def _gen_messy_schedule() -> bytes:
    """A payload whose rent schedule overlaps + disagrees with NOI (a real broker defect)."""
    p = _sample()
    lease = p["lease"]
    lease["rentSchedule"][1]["periodStart"] = "2028-01-01"  # overlaps period 0's end
    return json.dumps(p, ensure_ascii=True).encode()


def _gen_empty_payload() -> bytes:
    """A minimal required-only payload (no optional facts)."""
    minimal = {
        "@context": ["https://schema.org", "https://openom.app/ns/0.1"],
        "@type": "RealEstateListing",
        "specVersion": "0.1",
        "assertedBy": {"broker": "A", "brokerage": "B", "license": "C"},
        "assertedDate": "2026-08-16",
        "meta": {"supersedes": None},
    }
    return json.dumps(minimal, ensure_ascii=True).encode()


def _gen_cmyk_smask() -> bytes:
    """A PDF carrying a CMYK image and an alpha (SMask) image."""
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=200, height=200)
        cmyk = pymupdf.Pixmap(pymupdf.csCMYK, pymupdf.IRect(0, 0, 32, 32))
        cmyk.set_rect(cmyk.irect, (0, 255, 255, 0))
        page.insert_image(pymupdf.Rect(10, 10, 90, 90), pixmap=cmyk)
        alpha = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 32, 32), True)
        alpha.set_rect(alpha.irect, (255, 0, 0, 128))
        page.insert_image(pymupdf.Rect(100, 100, 180, 180), pixmap=alpha)
        return doc.tobytes()
    finally:
        doc.close()


def _gen_flattened_scan() -> bytes:
    """An image-only (rasterized) page - no text layer."""
    src = pymupdf.open()
    out = pymupdf.open()
    try:
        page = src.new_page(width=300, height=300)
        page.insert_text((36, 36), "scanned page content " * 8, fontsize=10)
        pix = src.load_page(0).get_pixmap(dpi=100)
        dst = out.new_page(width=300, height=300)
        dst.insert_image(dst.rect, pixmap=pix)
        return out.tobytes()
    finally:
        src.close()
        out.close()


def _gen_hash_mismatch() -> bytes:
    """An embedded OM whose XMP hash does not match the stored om.json (tampered)."""
    embedded = embed(_base_pdf(), _sample(), asserted_date="2026-08-15")
    with pikepdf.open(io.BytesIO(embedded)) as pdf:
        write_marker(
            pdf, spec_version="0.1", payload_filename="om.json",
            payload_hash="sha256:" + "0" * 64, asserted_date="2026-08-15",
        )
        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()


PATHOLOGY_GENERATORS = {
    "messy-schedule": _gen_messy_schedule,
    "empty-payload": _gen_empty_payload,
    "cmyk-smask": _gen_cmyk_smask,
    "flattened-scan": _gen_flattened_scan,
    "hash-mismatch": _gen_hash_mismatch,
}


def build_pathologies() -> dict[str, bytes]:
    """Generate every pathology fixture; a generator that returns empty bytes is a gap."""
    return {name: gen() for name, gen in PATHOLOGY_GENERATORS.items()}


# --- producer axis (from the real corpus /Producer metadata) ---------------------------

def _classify_producer(pdf_bytes: bytes) -> str:
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            producer = str(pdf.docinfo.get("/Producer", "")) + str(pdf.docinfo.get("/Creator", ""))
    except Exception:  # noqa: BLE001 - unreadable corpus file is simply unclassified
        return "other"
    p = producer.lower()
    if "indesign" in p:
        return "indesign"
    if "word" in p or "microsoft" in p:
        return "word"
    if "buildout" in p:
        return "buildout"
    return "other"


def scan_corpus() -> dict[str, list[str]]:
    """Bucket every corpus PDF by producer; 'scanned' is detected structurally (no text)."""
    buckets: dict[str, list[str]] = defaultdict(list)
    if not OMS.exists():
        return buckets
    for pdf_path in sorted(OMS.rglob("*.pdf")):
        data = pdf_path.read_bytes()
        rel = pdf_path.relative_to(OMS).as_posix()
        buckets[_classify_producer(data)].append(rel)
        # 'scanned' is a structural class (orthogonal to the producer tool): use the canonical
        # classifier so it matches om_inspect (textCoverage < 0.20), not a strict no-text rule.
        try:
            if _inspect(data)["class"] == "scanned":
                buckets["scanned"].append(rel)
        except Exception:  # noqa: BLE001 - unreadable corpus file is simply unclassified
            pass
    return buckets


def assert_matrix(*, require_corpus: bool) -> list[str]:
    """Return the list of unfilled cells (empty = matrix is full)."""
    gaps: list[str] = []
    pathologies = build_pathologies()
    for name in PATHOLOGIES:
        if not pathologies.get(name):
            gaps.append(f"pathology:{name}")
    if require_corpus:
        buckets = scan_corpus()
        for producer in PRODUCERS:
            if not buckets.get(producer):
                gaps.append(f"producer:{producer}")
    return gaps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assert-full", action="store_true", help="both axes (needs OMs/)")
    parser.add_argument("--assert-synthetic", action="store_true", help="pathology axis only")
    args = parser.parse_args()

    require_corpus = args.assert_full or (not args.assert_synthetic and OMS.exists())
    pathologies = build_pathologies()
    buckets = scan_corpus() if require_corpus else {}  # the corpus scan is heavy - skip when unused

    print("PATHOLOGY axis (synthetic):")
    for name in PATHOLOGIES:
        mark = "x" if pathologies.get(name) else " "
        print(f"  [{mark}] {name} ({len(pathologies.get(name, b''))} bytes)")
    print("PRODUCER axis (corpus /Producer):")
    for producer in PRODUCERS:
        n = len(buckets.get(producer, []))
        print(f"  [{'x' if n else ' '}] {producer} ({n} real OMs)")

    if args.assert_full or args.assert_synthetic:
        gaps = assert_matrix(require_corpus=require_corpus)
        if gaps:
            print(f"\nMATRIX INCOMPLETE - empty cells: {gaps}")
            print("(producer cells need real OMs under OMs/ - Q3; pathologies are synthetic)")
            return 1
        print("\nMATRIX FULL - every cell filled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
