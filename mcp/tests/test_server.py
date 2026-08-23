"""M1 /mcp server wiring - all seven tools registered + delegating to the pure bodies."""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from typing import Any

import pikepdf
import pymupdf

from openom_mcp import server

SPEC = Path(__file__).resolve().parents[2] / "spec"
EXPECTED = [
    "om_embed",
    "om_extract_images",
    "om_extract_text",
    "om_inspect",
    "om_read",
    "om_request_upload",
    "om_validate",
]


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def _blank(path: Path) -> Path:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    buf = io.BytesIO()
    pdf.save(buf)
    path.write_bytes(buf.getvalue())
    return path


def _text(path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "offering text layer " * 40, fontsize=11)
    path.write_bytes(doc.tobytes())
    doc.close()
    return path


def test_all_seven_tools_registered() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    assert sorted(t.name for t in tools) == EXPECTED


def test_assertions_not_facts_reaches_the_llm_description() -> None:
    """[Ma2] The safety contract MUST be in the tool `description` the model sees (built from the
    server.py wrapper docstring), not only in tools.py delegates the LLM never receives."""
    tools = {t.name: (t.description or "") for t in asyncio.run(server.mcp.list_tools())}
    read = tools["om_read"].lower()
    # the contract must be in the description the model receives, not just in tools.py internals
    assert "assert" in read and "unaltered" in read, tools["om_read"]
    assert ("not that its figures are true" in read) or ("verified fact" in read), tools["om_read"]
    assert "market truth" in tools["om_validate"].lower()
    # single-sourced (Ma2): the description is built FROM the tools.py delegate docstring, so it
    # cannot drift from the pure API. The terse server wrapper docstring is NOT the description.
    from openom_mcp import tools as _t

    assert (_t.om_read.__doc__ or "").strip() in tools["om_read"]
    assert tools["om_read"] != (server.om_read.__doc__ or "")


def test_server_tools_delegate(tmp_path: Path) -> None:
    ref = {"path": str(_text(tmp_path / "t.pdf"))}
    assert server.om_inspect(ref)["class"] in {"native", "hybrid", "scanned"}
    assert "payload" in server.om_read(ref)
    assert "text" in server.om_extract_text(ref, maxChars=50)
    assert "manifest" in server.om_extract_images(ref, outDir=str(tmp_path / "o"))
    assert server.om_validate(_sample())["ok"] is True
    out = server.om_embed(
        {"path": str(_blank(tmp_path / "b.pdf"))}, _sample(), outPath=str(tmp_path / "out.pdf")
    )
    assert out["xmp"]["specName"] == "openOM"
