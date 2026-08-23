"""DX fixes: --version (Mi14), embed --validate (Mi10) + --mirror/stdout warning (Mi9),
mirror exit-code consistency (Mi11), conformance friendly error (Mi8)."""

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


def test_version_flag() -> None:
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0
    assert "openom-cli" in r.stdout and "spec" in r.stdout


def test_embed_validate_blocks_schema_invalid(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "b.pdf")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"@type": "RealEstateListing"}), encoding="utf-8")  # missing required
    r = runner.invoke(
        app,
        ["embed", str(base), "--payload", str(bad), "--out", str(tmp_path / "o.pdf"),
         "--asserted-date", "2026-01-01", "--validate"],
    )
    assert r.exit_code == 1  # schema errors block


def test_embed_valid_with_validate_succeeds(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "b.pdf")
    sample = SPEC / "samples" / "valid-stnl.json"
    r = runner.invoke(
        app,
        ["embed", str(base), "--payload", str(sample), "--out", str(tmp_path / "o.pdf"),
         "--asserted-date", "2026-01-01", "--validate"],
    )
    assert r.exit_code == 0


def test_mirror_on_non_om_pdf_exits_3(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "plain.pdf")  # no embedded payload
    r = runner.invoke(app, ["mirror", str(base)])
    assert r.exit_code == 3  # OM-IO-ABSENT, consistent with `check`


def test_conformance_missing_spec_dir_is_friendly(tmp_path: Path) -> None:
    r = runner.invoke(app, ["conformance", "--spec-dir", str(tmp_path / "nope")])
    assert r.exit_code == 3
    assert "conformance vectors not found" in (r.stdout + str(r.stderr))


def test_conformance_impl_dir_empty_fails_not_false_passes(tmp_path: Path) -> None:
    # [Mi3] An impl that produced NO output must FAIL, never silently pass with 0 checks.
    r = runner.invoke(app, ["conformance", "--spec-dir", str(SPEC), "--impl-dir", str(tmp_path)])
    assert r.exit_code == 1


def test_conformance_impl_dir_correct_output_passes(tmp_path: Path) -> None:
    from openom_core import canonicalize

    manifest = json.loads((SPEC / "vectors" / "manifest.json").read_text(encoding="utf-8"))
    for vec in manifest["vectors"]:
        payload = json.loads((SPEC / "vectors" / vec["payload"]).read_text(encoding="utf-8"))
        (tmp_path / f"{vec['name']}.canonical").write_bytes(canonicalize(payload))
    r = runner.invoke(
        app, ["--quiet", "conformance", "--spec-dir", str(SPEC), "--impl-dir", str(tmp_path)]
    )
    assert r.exit_code == 0
