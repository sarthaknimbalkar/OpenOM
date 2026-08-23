"""[Ma4] The self-hosted server's om_read/om_validate result keys MUST match the cross-server
contract (spec/mcp-tool-contract.json) that the public Worker also conforms to (as a superset). This
is the recurrence guard for the om_read shape divergence that appeared twice (Ma9, then Ma4)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf
from openom_core.embed import embed

from openom_mcp import tools

ROOT = Path(__file__).resolve().parents[2]
_C = (ROOT / "spec" / "mcp-tool-contract.json").read_text(encoding="utf-8")
CONTRACT = json.loads(_C)["tools"]
SAMPLE = json.loads((ROOT / "spec" / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def _embedded_pdf(tmp: Path) -> str:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    buf = io.BytesIO()
    pdf.save(buf)
    out = embed(buf.getvalue(), SAMPLE, asserted_date=str(SAMPLE["assertedDate"]))
    p = tmp / "e.pdf"
    p.write_bytes(out)
    return str(p)


def test_om_read_keys_match_contract(tmp_path: Path) -> None:
    res = tools.om_read({"path": _embedded_pdf(tmp_path)})
    assert set(CONTRACT["om_read"]["requiredKeys"]).issubset(res), res.keys()


def test_om_validate_keys_match_contract() -> None:
    res = tools.om_validate(SAMPLE)
    assert set(CONTRACT["om_validate"]["requiredKeys"]).issubset(res), res.keys()
