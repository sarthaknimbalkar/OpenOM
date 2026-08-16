"""Task 11: the om CLI over openom-core."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf
from typer.testing import CliRunner

from openom_cli.main import app

runner = CliRunner()
SPEC = Path(__file__).resolve().parents[2] / "spec"


def _base_pdf(path: Path) -> Path:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    buf = io.BytesIO()
    pdf.save(buf)
    path.write_bytes(buf.getvalue())
    return path


def test_embed_then_read(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "base.pdf")
    sample = SPEC / "samples" / "valid-stnl.json"
    out = tmp_path / "out.pdf"
    r1 = runner.invoke(
        app,
        ["embed", str(base), "--payload", str(sample), "--out", str(out),
         "--asserted-date", "2026-08-15"],
    )
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(app, ["read", str(out)])
    assert r2.exit_code == 0, r2.output
    parsed = json.loads(r2.output)
    assert parsed["present"] is True
    assert parsed["verification"]["hashValid"] is True


def test_embed_warns_on_backwards_asserted_date(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "base.pdf")
    stnl = SPEC / "samples" / "valid-stnl.json"
    proforma = SPEC / "samples" / "valid-proforma.json"  # a different payload
    out1 = tmp_path / "out1.pdf"
    out2 = tmp_path / "out2.pdf"
    runner.invoke(
        app,
        ["embed", str(base), "--payload", str(stnl), "--out", str(out1),
         "--asserted-date", "2026-08-15"],
    )
    r = runner.invoke(
        app,
        ["embed", str(out1), "--payload", str(proforma), "--out", str(out2),
         "--asserted-date", "2026-07-01"],  # earlier than the prior marker
    )
    assert r.exit_code == 0, r.output
    assert "OMW-W051" in r.output


def test_validate_valid_exits_zero(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        ["validate", str(SPEC / "samples" / "valid-stnl.json"),
         "--schema", str(SPEC / "om-0.1.schema.json")],
    )
    assert r.exit_code == 0
    assert json.loads(r.output)["ok"] is True


def test_validate_invalid_exits_nonzero(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        ["validate", str(SPEC / "samples" / "invalid-missing-noitype.json"),
         "--schema", str(SPEC / "om-0.1.schema.json")],
    )
    assert r.exit_code == 1
    assert "OMV-E002" in r.output


def test_inspect(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "b.pdf")
    r = runner.invoke(app, ["inspect", str(base)])
    assert r.exit_code == 0
    assert json.loads(r.output)["class"] in {"native", "hybrid", "scanned"}
