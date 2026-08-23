"""In-flow guidance for the non-technical broker: `om init`, `om profile`,
plain-English validation coaching, and friendly embed errors that always name the next action.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openom_cli import profile as _profile
from openom_cli import scaffold
from openom_cli.humanize import footer, humanize_finding, humanize_path
from openom_cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the profile config at a temp dir so tests never touch the real %APPDATA%."""
    monkeypatch.setattr(_profile, "config_dir", lambda: tmp_path / "cfg")


# --- om init --------------------------------------------------------------------------------------
def test_init_writes_a_valid_scaffold(tmp_path: Path) -> None:
    out = tmp_path / "deal.json"
    r = runner.invoke(app, ["init", str(out)])
    assert r.exit_code == 0, r.output
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["@type"] == "RealEstateListing"
    assert doc["deal"]["capRate"] == 0.0625  # the decimal, not 6.25
    # the scaffold validates clean out of the box
    v = runner.invoke(app, ["--quiet", "validate", str(out)])
    assert v.exit_code == 0, v.output


def test_init_guidance_calls_out_the_caprate_trap(tmp_path: Path) -> None:
    r = runner.invoke(app, ["init", str(tmp_path / "deal.json")])
    assert "DECIMAL fraction: 6.25% = 0.0625" in r.output
    assert "openom.app/embed/" in r.output


def test_init_refuses_to_clobber_without_force(tmp_path: Path) -> None:
    out = tmp_path / "deal.json"
    out.write_text("{}", encoding="utf-8")
    r = runner.invoke(app, ["init", str(out)])
    assert r.exit_code == 3
    assert "--force" in r.output
    assert runner.invoke(app, ["init", str(out), "--force"]).exit_code == 0


def test_init_rejects_unknown_template(tmp_path: Path) -> None:
    r = runner.invoke(app, ["init", str(tmp_path / "d.json"), "--template", "warehouse"])
    assert r.exit_code == 2
    assert "unknown template" in r.output


@pytest.mark.parametrize("template", ["stnl", "multifamily", "proforma"])
def test_every_template_validates_clean(tmp_path: Path, template: str) -> None:
    out = tmp_path / f"{template}.json"
    assert runner.invoke(app, ["init", str(out), "--template", template]).exit_code == 0
    assert runner.invoke(app, ["--quiet", "validate", str(out)]).exit_code == 0


def test_init_fills_assertedby_from_saved_profile(tmp_path: Path) -> None:
    runner.invoke(app, ["profile", "set", "--broker", "Jane B", "--brokerage", "Acme"])
    out = tmp_path / "deal.json"
    r = runner.invoke(app, ["init", str(out)])
    assert "filled from your saved profile" in r.output
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["assertedBy"]["broker"] == "Jane B"
    assert doc["assertedBy"]["brokerage"] == "Acme"


# --- om profile -----------------------------------------------------------------------------------
def test_profile_set_show_roundtrip() -> None:
    s = runner.invoke(app, ["profile", "set", "--broker", "Jane", "--license", "MI 1"])
    assert s.exit_code == 0
    assert "Saved your broker profile" in s.output
    show = runner.invoke(app, ["profile", "show"])
    assert show.exit_code == 0
    assert '"broker": "Jane"' in show.output


def test_profile_set_with_nothing_is_a_usage_error() -> None:
    r = runner.invoke(app, ["profile", "set"])
    assert r.exit_code == 2
    assert "nothing to set" in r.output


def test_profile_show_when_empty_guides_not_errors() -> None:
    r = runner.invoke(app, ["profile", "show"])
    assert r.exit_code == 0
    assert "No profile saved yet" in r.output


def test_profile_path_prints_location() -> None:
    r = runner.invoke(app, ["profile", "path"])
    assert r.exit_code == 0
    assert "profile.json" in r.output


# --- embed friendly errors ------------------------------------------------------------------------
def test_embed_with_no_args_explains_and_routes_to_browser() -> None:
    r = runner.invoke(app, ["embed"])
    assert r.exit_code == 2
    assert "om init" in r.output
    assert "openom.app/embed/" in r.output


def test_embed_missing_input_pdf(tmp_path: Path) -> None:
    p = tmp_path / "deal.json"
    p.write_text("{}", encoding="utf-8")
    r = runner.invoke(
        app, ["embed", "nope.pdf", "--payload", str(p), "--out", "o.pdf",
              "--asserted-date", "2026-08-24"],
    )
    assert r.exit_code == 3
    assert "input PDF not found" in r.output


def test_embed_missing_payload_points_at_om_init(tmp_path: Path) -> None:
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.7\n%%EOF\n")
    r = runner.invoke(
        app, ["embed", str(pdf), "--payload", "gone.json", "--out", "o.pdf",
              "--asserted-date", "2026-08-24"],
    )
    assert r.exit_code == 3
    assert "payload file not found" in r.output
    assert "om init" in r.output


def test_embed_merges_profile_into_payload(tmp_path: Path) -> None:
    """A payload with no assertedBy gets it from the saved profile at embed time."""
    import pikepdf

    runner.invoke(app, ["profile", "set", "--broker", "Jane B"])
    pdf = tmp_path / "in.pdf"
    with pikepdf.Pdf.new() as p:
        p.add_blank_page()
        p.save(str(pdf))
    payload = tmp_path / "deal.json"
    payload.write_text(
        json.dumps({"@context": ["https://schema.org", "https://openom.app/ns/0.1"],
                    "@type": "RealEstateListing", "assertedDate": "2026-08-24",
                    "deal": {"status": "active"}}),
        encoding="utf-8",
    )
    out = tmp_path / "out.pdf"
    r = runner.invoke(
        app, ["embed", str(pdf), "--payload", str(payload), "--out", str(out),
              "--asserted-date", "2026-08-24"],
    )
    assert r.exit_code == 0, r.output
    assert "saved profile" in r.output
    read = runner.invoke(app, ["read", str(out)])
    assert '"broker": "Jane B"' in read.output


# --- humanized validation coaching ----------------------------------------------------------------
def test_validate_humanizes_the_caprate_trap(tmp_path: Path) -> None:
    out = tmp_path / "deal.json"
    runner.invoke(app, ["init", str(out)])
    doc = json.loads(out.read_text(encoding="utf-8"))
    doc["deal"]["capRate"] = 6.25
    out.write_text(json.dumps(doc), encoding="utf-8")
    r = runner.invoke(app, ["validate", str(out)])
    assert r.exit_code == 1
    assert "decimal fraction" in r.output
    assert "0.0625" in r.output


# --- pure-unit coverage of the helpers ------------------------------------------------------------
def test_humanize_path() -> None:
    assert humanize_path("/deal/capRate") == "deal > cap rate"
    assert humanize_path("/lease/rentSchedule/0/rentPSF") == "lease > rent schedule > #1 > rent PSF"
    assert humanize_path("/") == "(payload root)"


def test_humanize_finding_branches() -> None:
    assert "decimal fraction" in humanize_finding("OMV-E001", "/deal/capRate", "raw")
    assert "in-place" in humanize_finding("OMV-E002", "/deal/noiType", "raw")
    assert "ISO 4217" in humanize_finding("OMV-E001", "/currency", "raw")
    generic = humanize_finding("OMV-E001", "/property/buildingSF", "must be a number")
    assert "building SF" in generic and "(OMV-E001)" in generic
    assert "om init" in footer()


def test_profile_merge_payload_wins_and_fills_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _profile, "profile_asserted_by",
        lambda: {"broker": "Saved", "brokerage": "SavedCo", "license": "L1"},
    )
    payload = {"assertedBy": {"broker": "Typed"}}
    assert _profile.merge_into(payload) is True
    assert payload["assertedBy"]["broker"] == "Typed"  # payload wins
    assert payload["assertedBy"]["brokerage"] == "SavedCo"  # gap filled
    # no profile -> no change
    monkeypatch.setattr(_profile, "profile_asserted_by", dict)
    assert _profile.merge_into({"assertedBy": {}}) is False


def test_scaffold_build_skeleton_stamps_and_merges() -> None:
    doc = scaffold.build_skeleton(
        "stnl", today="2026-08-24", profile_asserted_by={"broker": "X"}
    )
    assert doc["assertedDate"] == "2026-08-24"
    assert doc["deal"]["noiAsOfDate"] == "2026-08-24"
    assert doc["assertedBy"]["broker"] == "X"
    with pytest.raises(KeyError):
        scaffold.build_skeleton("nope", today="2026-08-24")


def test_load_profile_survives_corrupt_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_profile, "config_dir", lambda: tmp_path)
    _profile.profile_path().write_text("{ not json", encoding="utf-8")
    assert _profile.load_profile() == {}  # never raises
