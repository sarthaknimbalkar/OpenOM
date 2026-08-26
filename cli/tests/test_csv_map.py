"""Cover the CSV->openOM mapper (pure, deterministic - the spreadsheet on-ramp for bulk seeding)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

import jsonschema
import pikepdf
from typer.testing import CliRunner

from openom_cli.csv_map import (
    CANONICAL_COLUMNS,
    override_identity,
    row_to_payload,
    template_csv,
)
from openom_cli.main import app

_runner = CliRunner()

SPEC = Path(__file__).resolve().parents[2] / "spec"


def _schema() -> dict[str, Any]:
    return json.loads((SPEC / "om-0.1.schema.json").read_text(encoding="utf-8"))


_BY = {"broker": "Jane Example", "brokerage": "Example Advisors", "license": "TX 12345"}


def _map(row: dict[str, str]) -> dict[str, Any]:
    return row_to_payload(
        row, asserted_by=_BY, asserted_date="2026-08-15", noi_type="in-place"
    )


def test_full_row_maps_to_a_schema_valid_payload() -> None:
    row = {
        "id": "123-main", "pdf": "123-main.pdf",
        "streetAddress": "123 Main St", "city": "Austin", "state": "TX - Texas",
        "postalCode": "78701", "propertyType": "Retail", "buildingSF": "9,100",
        "yearBuilt": "2019", "askingPrice": "1,850,000", "capRatePct": "6.25", "noi": "115625",
        "tenant": "Example Retail, LLC", "leaseType": "NNN Lease",
        "commencement": "5/1/2019", "expiration": "4/30/2034",
    }
    payload = _map(row)
    jsonschema.Draft202012Validator(_schema()).validate(payload)  # raises if invalid
    assert payload["deal"]["capRate"] == 0.0625  # percent -> fraction
    assert payload["deal"]["askingPrice"] == 1850000  # commas stripped
    assert payload["property"]["address"]["addressRegion"] == "TX"  # 'TX - Texas' -> 'TX'
    assert payload["property"]["propertyType"] == "retail"  # lowercased
    assert payload["lease"]["leaseTypeAsserted"] == "NNN"
    assert payload["lease"]["commencement"] == "2019-05-01"  # M/D/Y -> ISO
    assert payload["lease"]["termMonths"] == 179  # derived, deterministic
    assert payload["property"]["address"]["addressCountry"] == "US"  # defaulted from a US state
    assert payload["deal"]["pricePerSF"] == round(1850000 / 9100, 2)  # derived


def test_iso_dates_pass_through() -> None:
    payload = _map({"commencement": "2019-05-01", "expiration": "2034-04-30"})
    assert payload["lease"]["commencement"] == "2019-05-01"
    assert payload["lease"]["expiration"] == "2034-04-30"


def test_malformed_dates_are_dropped_not_crashed() -> None:
    # A garbled ISO-looking date or an unparseable value is omitted (never a crash, never a guess).
    payload = _map({"askingPrice": "1000000", "commencement": "2019-13-40", "expiration": "later"})
    assert "commencement" not in payload.get("lease", {})
    assert "expiration" not in payload.get("lease", {})
    # a 4-digit-year, 3-part value with non-integer parts hits the ISO parse-failure branch
    assert "lease" not in _map({"askingPrice": "1", "commencement": "20x9-05-01"})


def test_absent_cells_are_omitted_never_guessed() -> None:
    payload = _map({"askingPrice": "1000000"})  # nothing else
    assert "capRate" not in payload["deal"]
    assert "lease" not in payload  # no lease cells -> no lease object
    assert "property" not in payload  # no property cells -> no property object
    assert payload["assertedBy"] == _BY  # identity stamped verbatim


def test_blank_cells_treated_as_absent() -> None:
    payload = _map({"askingPrice": "1000000", "capRatePct": "  ", "tenant": ""})
    assert "capRate" not in payload["deal"]
    assert "lease" not in payload


def test_override_identity_reads_only_present_override_columns() -> None:
    row = {"broker": "Sam Other", "askingPrice": "1", "city": "Austin"}
    assert override_identity(row) == {"broker": "Sam Other"}
    assert override_identity({"askingPrice": "1"}) == {}


def test_template_has_headers_and_one_example_row() -> None:
    text = template_csv()
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == list(CANONICAL_COLUMNS)  # header is the canonical vocabulary
    assert len(rows) == 2  # header + one worked example
    # the example row itself maps to a schema-valid payload
    example = dict(zip(CANONICAL_COLUMNS, rows[1], strict=True))
    jsonschema.Draft202012Validator(_schema()).validate(_map(example))


# --- end-to-end CLI: the full spreadsheet on-ramp (csv-manifest -> embed-batch -> read) ---
def _blank_pdf(path: Path) -> None:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    buf = io.BytesIO()
    pdf.save(buf)
    path.write_bytes(buf.getvalue())


def test_csv_manifest_one_bad_row_is_skipped_not_a_batch_abort(tmp_path: Path) -> None:
    # A single pathological cell (1e400 -> non-finite) must skip that row with a reason, never abort
    # the whole bulk-seed batch or traceback.
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _blank_pdf(pdf_dir / "good.pdf")
    _blank_pdf(pdf_dir / "bad.pdf")
    csv_file = tmp_path / "c.csv"
    csv_file.write_text(
        "id,askingPrice,noi\ngood,1850000,115625\nbad,1e400,1e400\n", encoding="utf-8"
    )
    out = tmp_path / "mapped"
    r = _runner.invoke(
        app,
        ["csv-manifest", "--csv", str(csv_file), "--pdf-dir", str(pdf_dir), "--out-dir", str(out),
         "--broker", "J", "--brokerage", "A", "--license", "L",
         "--asserted-date", "2026-08-15", "--noi-type", "in-place"],
    )
    assert r.exit_code == 0, r.output
    summary = json.loads(r.output[r.output.index("{"):])
    # 'good' maps; 'bad' maps too but with the non-finite cells simply omitted (never a crash).
    assert summary["mapped"] == 2
    good = json.loads((out / "good.om.json").read_text(encoding="utf-8"))
    assert good["deal"]["askingPrice"] == 1850000
    bad = json.loads((out / "bad.om.json").read_text(encoding="utf-8"))
    assert "askingPrice" not in bad.get("deal", {})  # the 1e400 cell was dropped, not embedded


def test_csv_manifest_template_then_embed_batch_roundtrip(tmp_path: Path) -> None:
    # 1) --template writes a fillable CSV; a broker fills two rows.
    tmpl = tmp_path / "template.csv"
    r0 = _runner.invoke(app, ["csv-manifest", "--template", str(tmpl)])
    assert r0.exit_code == 0, r0.output
    assert tmpl.read_text(encoding="utf-8").splitlines()[0].startswith("id,pdf,")

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _blank_pdf(pdf_dir / "deal-1.pdf")
    _blank_pdf(pdf_dir / "deal-2.pdf")
    csv_file = tmp_path / "catalog.csv"
    csv_file.write_text(
        "id,streetAddress,city,state,askingPrice,capRatePct,noi\n"
        "deal-1,1 A St,Austin,TX,1850000,6.25,115625\n"
        "deal-2,2 B St,Dallas,TX,2400000,7.0,168000\n"
        "deal-3,3 C St,Waco,TX,900000,8,72000\n",  # deal-3 has no PDF -> skipped
        encoding="utf-8",
    )
    out = tmp_path / "mapped"
    r1 = _runner.invoke(
        app,
        ["csv-manifest", "--csv", str(csv_file), "--pdf-dir", str(pdf_dir), "--out-dir", str(out),
         "--broker", "Jane Example", "--brokerage", "Example Advisors", "--license", "TX 12345",
         "--asserted-date", "2026-08-15", "--noi-type", "in-place"],
    )
    assert r1.exit_code == 0, r1.output
    summary = json.loads(r1.output[r1.output.index("{"):])
    assert summary["mapped"] == 2
    assert any(s["id"] == "deal-3" for s in summary["skipped"])  # no PDF -> skipped with a reason

    # 2) embed-batch consumes the produced manifest; both OMs round-trip hash-valid.
    r2 = _runner.invoke(
        app,
        ["embed-batch", "--manifest", str(out / "manifest.json"),
         "--out-dir", str(tmp_path / "embedded")],
    )
    assert r2.exit_code == 0, r2.output
    for name in ("deal-1.pdf", "deal-2.pdf"):
        rr = _runner.invoke(app, ["read", str(tmp_path / "embedded" / name)])
        assert rr.exit_code == 0, rr.output
        got = json.loads(rr.output)
        assert got["verification"]["hashValid"] is True
        assert got["payload"]["assertedBy"]["broker"] == "Jane Example"
