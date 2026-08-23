"""[Mi22/Mi1] Guard the AI-builder docs against stale/made-up content: the grounding-ai worked
example must cite the ACTUAL asserted values of the sample OM (a made-up number is exactly the
hallucination openOM exists to prevent), and the generated extraction-playbook page must not carry a
wrong tool-call signature (om_embed(...assertedDate) / om_validate(...schema))."""

from __future__ import annotations

import re
from pathlib import Path

from openom_core.embed import read

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
SAMPLE = ROOT / "spec" / "assets" / "openom-sample.pdf"


def test_grounding_example_matches_the_real_sample_om() -> None:
    r = read(SAMPLE.read_bytes())
    deal = (r.payload or {}).get("deal", {})
    noi = deal["noi"]
    as_of = deal["noiAsOfDate"]
    page = (SITE / "docs" / "grounding-ai.html").read_text(encoding="utf-8")
    assert f"{noi:,}" in page, f"grounding example NOI is stale vs the sample OM ({noi})"
    assert as_of in page, f"grounding example noiAsOfDate is stale vs the sample OM ({as_of})"


def test_extraction_playbook_page_has_no_wrong_tool_calls() -> None:
    page = (SITE / "docs" / "extraction-playbook.html").read_text(encoding="utf-8")
    assert not re.search(r"om_embed\([^)]*assertedDate", page)
    assert not re.search(r"om_validate\([^)]*schema", page)
