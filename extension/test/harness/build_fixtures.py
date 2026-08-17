# SPDX-License-Identifier: MIT
"""Generate the labeled §AA fixtures for the M5a-B Playwright consumer gate.

Each fixture is a PDF the extension re-fetches + reads, plus (where relevant) the origin `om.json`
mirror the extension fetches for domain-origin verification. Reuses the tested Python core
(openom_core.embed) so the fixtures are real embeds. Regenerate with:
    python extension/test/harness/build_fixtures.py
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf

from openom_core.canonical import canonicalize, payload_hash
from openom_core.embed import embed

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "fixtures"
SAMPLE = json.loads((ROOT / "spec" / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def _blank() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(300, 300))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def _write(rel: str, data: bytes) -> None:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def _tamper(payload: dict, date: str) -> bytes:
    """Embed `payload`, then overwrite the om.json stream with DIFFERENT-but-valid canonical bytes,
    leaving the XMP payloadHash marker stale → a clean hash-mismatch that still parses as JSON."""
    embedded = embed(_blank(), payload, asserted_date=date)
    altered = json.loads(json.dumps(payload))
    altered["deal"]["askingPrice"] = int(altered["deal"]["askingPrice"]) + 1  # changed, still valid
    with pikepdf.open(io.BytesIO(embedded)) as pdf:
        pdf.Root.Names.EmbeddedFiles.Names[1].EF.F.write(canonicalize(altered))
        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()


def main() -> None:
    date = str(SAMPLE["assertedDate"])
    # valid: embedded + matching mirror (canonical bytes) → origin-verified
    valid = embed(_blank(), SAMPLE, asserted_date=date)
    _write("valid/deal.pdf", valid)
    _write("valid/om.json", canonicalize(SAMPLE))

    # integrity: embedded, NO mirror served → integrity-ok
    _write("integrity/deal.pdf", embed(_blank(), SAMPLE, asserted_date=date))

    # tampered: embedded then stream overwritten (valid JSON, stale marker) → hash-mismatch
    _write("tampered/deal.pdf", _tamper(SAMPLE, date))

    # plain: no payload → absent
    _write("plain/deal.pdf", _blank())

    # stale: embed P1; mirror serves a NEWER superseding payload P2 → integrity-ok + OMW-W051
    stale_new = json.loads(json.dumps(SAMPLE))
    stale_new["assertedDate"] = "2027-01-01"
    stale_new["deal"]["askingPrice"] = 1750000
    stale_new["deal"]["capRate"] = round(stale_new["deal"]["noi"] / 1750000, 4)
    stale_new["meta"]["supersedes"] = payload_hash(SAMPLE)
    _write("stale/deal.pdf", embed(_blank(), SAMPLE, asserted_date=date))
    _write("stale/om.json", canonicalize(stale_new))

    # author (M5b-1): a plain OM the broker embeds from scratch, and an already-embedded OM to reprice.
    _write("author/plain.pdf", _blank())
    _write("author/embedded.pdf", embed(_blank(), SAMPLE, asserted_date=date))

    print(f"wrote fixtures to {OUT}")


if __name__ == "__main__":
    main()
