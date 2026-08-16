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


def test_check_payload_json(tmp_path: Path) -> None:
    # Consistency tier only (no schema): the valid sample is internally consistent -> exit 0.
    r = runner.invoke(app, ["check", str(SPEC / "samples" / "valid-stnl.json")])
    assert r.exit_code == 0, r.output
    parsed = json.loads(r.output)
    assert parsed["source"]["kind"] == "payload"
    assert parsed["warnings"] == []


def test_check_pdf_extracts_payload(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "base.pdf")
    sample = SPEC / "samples" / "valid-stnl.json"
    out = tmp_path / "out.pdf"
    runner.invoke(
        app,
        ["embed", str(base), "--payload", str(sample), "--out", str(out),
         "--asserted-date", "2026-08-15"],
    )
    r = runner.invoke(app, ["check", str(out)])
    assert r.exit_code == 0, r.output
    parsed = json.loads(r.output)
    assert parsed["source"]["kind"] == "pdf"
    assert parsed["source"]["hashValid"] is True


def test_check_strict_exits_nonzero_on_warnings(tmp_path: Path) -> None:
    bad = json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))
    bad["deal"]["capRate"] = 0.09  # inconsistent with NOI/price -> OMW-W010
    payload = tmp_path / "bad.json"
    payload.write_text(json.dumps(bad), encoding="utf-8")
    lax = runner.invoke(app, ["check", str(payload)])
    assert lax.exit_code == 0  # warnings never block by default
    strict = runner.invoke(app, ["check", str(payload), "--strict"])
    assert strict.exit_code == 1
    assert "OMW-W010" in strict.output


def test_check_as_of_drives_future_warning(tmp_path: Path) -> None:
    # assertedDate 2026-08-15 is in the future relative to an earlier processing date -> W032.
    r = runner.invoke(
        app,
        ["check", str(SPEC / "samples" / "valid-stnl.json"), "--as-of", "2020-01-01", "--strict"],
    )
    assert r.exit_code == 1
    assert "OMW-W032" in r.output


def test_check_pdf_without_payload_exits_cleanly(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "empty.pdf")
    r = runner.invoke(app, ["check", str(base)])
    assert r.exit_code == 3  # OM-IO-ABSENT, not a crash
    assert "Traceback" not in r.output


def test_inspect(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "b.pdf")
    r = runner.invoke(app, ["inspect", str(base)])
    assert r.exit_code == 0
    assert json.loads(r.output)["class"] in {"native", "hybrid", "scanned"}


def test_version() -> None:
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0
    parsed = json.loads(r.output)
    assert parsed["specVersion"] == "0.1"
    assert parsed["tool"] == "openom-cli"


def test_conformance_passes_over_spec() -> None:
    r = runner.invoke(app, ["conformance", "--spec-dir", str(SPEC)])
    assert r.exit_code == 0, r.output
    parsed = json.loads(r.output)
    assert parsed["ok"] is True
    assert parsed["failed"] == 0
    assert parsed["total"] > 0


def test_conformance_role_filter_runs_subset() -> None:
    full = json.loads(runner.invoke(app, ["conformance", "--spec-dir", str(SPEC)]).output)
    validator_only = json.loads(
        runner.invoke(app, ["conformance", "--spec-dir", str(SPEC), "--role", "validator"]).output
    )
    assert validator_only["ok"] is True
    assert validator_only["total"] <= full["total"]  # a filtered subset
    # A non-matching level filters out every vector, leaving only the sample checks.
    l2 = json.loads(
        runner.invoke(app, ["conformance", "--spec-dir", str(SPEC), "--level", "L2"]).output
    )
    assert l2["total"] < full["total"]


def test_conformance_detects_divergence(tmp_path: Path) -> None:
    vdir = tmp_path / "vectors"
    (vdir / "payloads").mkdir(parents=True)
    (vdir / "expected").mkdir(parents=True)
    (vdir / "payloads" / "x.json").write_text('{"a":1}', encoding="utf-8")
    (vdir / "expected" / "x.json").write_text(
        json.dumps({"jcs_sha256": "sha256:" + "0" * 64, "jcs_b64": "x"}), encoding="utf-8"
    )
    (vdir / "manifest.json").write_text(
        json.dumps(
            {
                "vectors": [
                    {"name": "x", "payload": "payloads/x.json",
                     "expected": "expected/x.json", "pdf": "pdfs/x.pdf", "dimensions": {}}
                ]
            }
        ),
        encoding="utf-8",
    )
    r = runner.invoke(app, ["conformance", "--spec-dir", str(tmp_path)])
    assert r.exit_code == 1  # a wrong expected hash MUST fail the suite
    assert "vector:x:jcs" in r.output


def test_extract_writes_images(tmp_path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40))
    pix.set_rect(pix.irect, (10, 20, 30))
    page.insert_image(pymupdf.Rect(10, 10, 90, 90), pixmap=pix)
    pdf_path = tmp_path / "img.pdf"
    pdf_path.write_bytes(doc.tobytes())
    doc.close()

    out_dir = tmp_path / "images"
    r = runner.invoke(app, ["extract", str(pdf_path), "--out-dir", str(out_dir)])
    assert r.exit_code == 0, r.output
    manifest = json.loads(r.output)
    assert any(d["error"] is None for d in manifest["images"])
    assert list(out_dir.glob("*.png"))


def test_bad_pdf_exits_cleanly(tmp_path: Path) -> None:
    bad = tmp_path / "not.pdf"
    bad.write_text("this is not a pdf", encoding="utf-8")
    r = runner.invoke(app, ["read", str(bad)])
    assert r.exit_code == 3  # data error, not a crash/traceback
    assert "Traceback" not in r.output


def test_missing_file_exits_cleanly(tmp_path: Path) -> None:
    r = runner.invoke(app, ["read", str(tmp_path / "nope.pdf")])
    assert r.exit_code == 3
