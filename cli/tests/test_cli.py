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


def test_embed_refuses_schema_invalid_by_default(tmp_path: Path) -> None:
    # Rule 6: a schema-invalid single-file embed must be refused by default (not silently stamped),
    # matching the browser author gate. capRate as a percentage (6.25) is the classic mistake.
    base = _base_pdf(tmp_path / "base.pdf")
    bad = json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))
    bad["deal"]["capRate"] = 6.25  # 625%, schema wants a 0-1 fraction
    payload = tmp_path / "bad.json"
    payload.write_text(json.dumps(bad), encoding="utf-8")
    out = tmp_path / "out.pdf"
    r = runner.invoke(app, ["embed", str(base), "--payload", str(payload), "--out", str(out),
                            "--asserted-date", "2026-08-15"])
    assert r.exit_code == 1, r.output
    assert not out.exists()  # nothing stamped
    assert "0.0625" in r.output or "OMV-E001" in r.output  # humanized capRate coaching or the code
    # --no-validate is the explicit escape for a deliberate draft
    r2 = runner.invoke(app, ["embed", str(base), "--payload", str(payload), "--out", str(out),
                             "--asserted-date", "2026-08-15", "--no-validate"])
    assert r2.exit_code == 0, r2.output
    assert out.exists()


def test_embed_batch_embeds_many_and_reports(tmp_path: Path) -> None:
    # Two valid OMs + one item with a missing PDF - the batch embeds the good ones, records the
    # failure, and exits non-zero. Proves the back-catalog seeding path end to end.
    sample = json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))
    (tmp_path / "data").mkdir()
    _base_pdf(tmp_path / "a.pdf")
    _base_pdf(tmp_path / "b.pdf")
    (tmp_path / "data" / "a.json").write_text(json.dumps(sample), encoding="utf-8")
    (tmp_path / "data" / "b.json").write_text(json.dumps(sample), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {"pdf": "a.pdf", "payload": "data/a.json"},
                {"pdf": "b.pdf", "payload": "data/b.json"},
                {"pdf": "missing.pdf", "payload": "data/a.json"},
            ]
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    r = runner.invoke(
        app,
        ["embed-batch", "--manifest", str(manifest), "--out-dir", str(out_dir),
         "--asserted-date", "2026-08-15"],
    )
    assert r.exit_code == 1, r.output  # one item failed → non-zero
    report = json.loads(r.output[r.output.index("{"):])
    assert report["total"] == 3 and report["counts"].get("embedded") == 2
    statuses = [x["status"] for x in report["results"]]
    assert statuses == ["embedded", "embedded", "error"]
    # the embedded outputs round-trip
    for name in ("a.pdf", "b.pdf"):
        rr = runner.invoke(app, ["read", str(out_dir / name)])
        assert rr.exit_code == 0
        assert json.loads(rr.output)["verification"]["hashValid"] is True


def test_embed_batch_skips_schema_invalid(tmp_path: Path) -> None:
    # With a schema, an invalid payload is SKIPPED (not embedded), per Rule 6 (schema errors block).
    _base_pdf(tmp_path / "a.pdf")
    (tmp_path / "bad.json").write_text(json.dumps({"specVersion": "0.1"}), encoding="utf-8")
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps([{"pdf": "a.pdf", "payload": "bad.json"}]), encoding="utf-8")
    r = runner.invoke(
        app,
        ["embed-batch", "--manifest", str(manifest), "--out-dir", str(tmp_path / "o"),
         "--asserted-date", "2026-08-15", "--schema", str(SPEC / "om-0.1.schema.json")],
    )
    assert r.exit_code == 1, r.output
    report = json.loads(r.output[r.output.index("{"):])
    assert report["counts"].get("embedded", 0) == 0
    assert report["results"][0]["status"] == "skipped"
    assert report["results"][0]["errors"]  # schema errors reported
    assert not (tmp_path / "o" / "a.pdf").exists()  # nothing written for a skipped item


def test_embed_batch_dir_mode_dry_run_and_resume(tmp_path: Path) -> None:
    # --dir pairs each PDF with a sibling .om.json; --dry-run writes nothing; a second run with
    # --skip-existing resumes without re-embedding.
    sample = (SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8")
    src = tmp_path / "in"
    src.mkdir()
    _base_pdf(src / "deal-a.pdf")
    (src / "deal-a.om.json").write_text(sample, encoding="utf-8")
    _base_pdf(src / "deal-b.pdf")
    (src / "deal-b.om.json").write_text(sample, encoding="utf-8")
    out = tmp_path / "pub"

    dry = runner.invoke(app, ["embed-batch", "--dir", str(src), "--out-dir", str(out),
                              "--asserted-date", "2026-08-15", "--dry-run"])
    assert dry.exit_code == 0, dry.output
    drep = json.loads(dry.output[dry.output.index("{"):])
    assert drep["dryRun"] is True and drep["counts"].get("would-embed") == 2
    assert not out.exists()  # dry-run wrote nothing

    real = runner.invoke(app, ["embed-batch", "--dir", str(src), "--out-dir", str(out),
                               "--asserted-date", "2026-08-15"])
    assert real.exit_code == 0, real.output
    assert (out / "deal-a.pdf").exists() and (out / "deal-b.pdf").exists()

    resume = runner.invoke(app, ["embed-batch", "--dir", str(src), "--out-dir", str(out),
                                 "--asserted-date", "2026-08-15", "--skip-existing"])
    assert resume.exit_code == 0, resume.output
    rrep = json.loads(resume.output[resume.output.index("{"):])
    assert rrep["counts"].get("skipped-existing") == 2  # resumed, nothing re-embedded


def test_embed_batch_requires_exactly_one_source(tmp_path: Path) -> None:
    r = runner.invoke(app, ["embed-batch", "--asserted-date", "2026-08-15"])
    assert r.exit_code == 2  # neither --manifest nor --dir


def test_buildout_manifest_bridge_end_to_end(tmp_path: Path) -> None:
    # The connector->manifest bridge on the Buildout listing shape: map -> manifest -> embed-batch.
    fixture = Path(__file__).parent / "fixtures" / "buildout-listing-sample.json"
    listings = tmp_path / "listings"
    listings.mkdir()
    (listings / "sample.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    pdfs = tmp_path / "oms"
    pdfs.mkdir()
    _base_pdf(pdfs / "sample.pdf")  # stands in for the fetched OM PDF
    staged = tmp_path / "staged"

    m = runner.invoke(app, [
        "buildout-manifest", "--listings-dir", str(listings), "--pdf-dir", str(pdfs),
        "--out-dir", str(staged), "--broker", "Jane Broker", "--brokerage", "Example Net Lease",
        "--license", "MI 0000", "--asserted-date", "2026-08-22", "--noi-type", "pro-forma",
    ])
    assert m.exit_code == 0, m.output
    # the mapped payload is schema-valid and internally consistent (NOI/price == capRate)
    payload = json.loads((staged / "sample.om.json").read_text(encoding="utf-8"))
    assert payload["deal"]["capRate"] == 0.0625
    assert payload["property"]["address"]["addressRegion"] == "MI"
    v = runner.invoke(app, ["validate", str(staged / "sample.om.json"),
                            "--schema", str(SPEC / "om-0.1.schema.json")])
    assert v.exit_code == 0, v.output  # schema-valid

    out = tmp_path / "embedded"
    b = runner.invoke(app, ["embed-batch", "--manifest", str(staged / "manifest.json"),
                            "--out-dir", str(out), "--schema", str(SPEC / "om-0.1.schema.json")])
    assert b.exit_code == 0, b.output
    rr = runner.invoke(app, ["read", str(out / "sample.pdf")])
    assert json.loads(rr.output)["payload"]["lease"]["tenantEntity"] == "Example Retail Stores, LLC"


def test_buildout_mapper_fills_and_derives_high_value_fields() -> None:
    # [M4] propertyType is mapped; pricePerUnit/pricePerSF/termMonths are derived deterministically.
    from openom_cli.buildout import listing_to_payload

    fixture = Path(__file__).parent / "fixtures" / "buildout-listing-sample.json"
    listing = json.loads(fixture.read_text(encoding="utf-8"))
    p = listing_to_payload(
        listing, asserted_by={"broker": "J", "brokerage": "B", "license": "L"},
        asserted_date="2026-08-22", noi_type="pro-forma",
    )
    assert p["property"]["propertyType"] == "retail"
    assert p["deal"]["pricePerUnit"] == 1_850_000  # 1,850,000 / 1 unit
    assert p["deal"]["pricePerSF"] == round(1_850_000 / 9100, 2)  # /9,100 SF
    assert p["lease"]["termMonths"] == 179  # 2019-05-01 → 2034-04-30


def test_buildout_manifest_overrides_and_coverage(tmp_path: Path) -> None:
    # M8: per-listing assertion identity (overrides) + a coverage report + reasoned skips.
    fixture = Path(__file__).parent / "fixtures" / "buildout-listing-sample.json"
    listings = tmp_path / "listings"
    listings.mkdir()
    (listings / "aaa.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    (listings / "bbb.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    (listings / "ccc.json").write_text("{}", encoding="utf-8")  # sparse + no pdf -> skipped
    pdfs = tmp_path / "oms"
    pdfs.mkdir()
    _base_pdf(pdfs / "aaa.pdf")
    _base_pdf(pdfs / "bbb.pdf")  # ccc has no pdf on purpose
    overrides = tmp_path / "ov.json"
    overrides.write_text(json.dumps({
        "bbb": {"broker": "Bob Other", "brokerage": "Other LLC",
                "license": "MI 9", "noiType": "in-place"}
    }), encoding="utf-8")
    staged = tmp_path / "staged"

    m = runner.invoke(app, [
        "buildout-manifest", "--listings-dir", str(listings), "--pdf-dir", str(pdfs),
        "--out-dir", str(staged), "--broker", "Jane Broker", "--brokerage", "Example NL",
        "--license", "MI 0", "--asserted-date", "2026-08-22", "--noi-type", "pro-forma",
        "--overrides", str(overrides),
    ])
    assert m.exit_code == 0, m.output
    a = json.loads((staged / "aaa.om.json").read_text(encoding="utf-8"))
    b = json.loads((staged / "bbb.om.json").read_text(encoding="utf-8"))
    assert a["assertedBy"]["broker"] == "Jane Broker" and a["deal"]["noiType"] == "pro-forma"
    assert b["assertedBy"]["broker"] == "Bob Other" and b["deal"]["noiType"] == "in-place"
    assert not (staged / "ccc.om.json").exists()  # skipped: no OM PDF
    cov = json.loads((staged / "coverage.json").read_text(encoding="utf-8"))
    assert {c["id"] for c in cov["listings"]} == {"aaa", "bbb"}
    assert all(c["filled"] >= 3 for c in cov["listings"])  # the real fixture is well-covered


def test_buildout_pull_orchestrator(tmp_path: Path) -> None:
    # B3: the pure pull() with a fake MCP transport + fake pdf fetch (deterministic, no network).
    from openom_cli.buildout_pull import pull

    listings = {
        "1": {"core": {"x": 1}, "om_url": "https://x.example/1.pdf"},
        "2": {"documents": [{"url": "https://x.example/2.pdf"}]},
        "3": {"core": {"no": "om"}},  # no discoverable pdf -> no-om
    }

    def get_listing(_tool: str, args: dict) -> dict:
        return listings[args["ref"]]

    def fetch_pdf(url: str) -> bytes:
        return f"%PDF-{url}".encode()

    out = tmp_path / "pull"
    summary = pull(
        ["1", "2", "3"], get_listing=get_listing, fetch_pdf=fetch_pdf,
        out_listings_dir=out / "listings", out_pdf_dir=out / "pdfs",
    )
    assert summary["pulled"] == 2
    statuses = {r["id"]: r["status"] for r in summary["results"]}
    assert statuses == {"1": "ok", "2": "ok", "3": "no-om"}
    assert (out / "listings" / "1.json").exists()
    assert (out / "pdfs" / "2.pdf").read_bytes() == b"%PDF-https://x.example/2.pdf"
    assert not (out / "pdfs" / "3.pdf").exists()


def test_buildout_pull_skip_existing_and_counts(tmp_path: Path) -> None:
    # Resume: an already-pulled listing is skipped (no re-fetch); counts summarize the run.
    from openom_cli.buildout_pull import pull

    out = tmp_path / "pull"
    (out / "listings").mkdir(parents=True)
    (out / "pdfs").mkdir(parents=True)
    (out / "listings" / "1.json").write_text("{}", encoding="utf-8")
    (out / "pdfs" / "1.pdf").write_bytes(b"%PDF-old")

    calls: list[str] = []

    def get_listing(_tool: str, args: dict) -> dict:
        calls.append(args["ref"])
        return {"om_url": f"https://x.example/{args['ref']}.pdf"}

    summary = pull(
        ["1", "2"], get_listing=get_listing, fetch_pdf=lambda u: b"%PDF-new",
        out_listings_dir=out / "listings", out_pdf_dir=out / "pdfs", skip_existing=True,
    )
    assert calls == ["2"]  # id 1 skipped, never fetched
    assert summary["counts"] == {"exists": 1, "ok": 1}
    assert (out / "pdfs" / "1.pdf").read_bytes() == b"%PDF-old"  # untouched


def test_buildout_pull_concurrent_preserves_order(tmp_path: Path) -> None:
    from openom_cli.buildout_pull import pull

    out = tmp_path / "pull"
    summary = pull(
        ["a", "b", "c", "d"],
        get_listing=lambda _t, args: {"om_url": f"https://x/{args['ref']}.pdf"},
        fetch_pdf=lambda u: b"%PDF-" + u.encode(),
        out_listings_dir=out / "listings", out_pdf_dir=out / "pdfs", jobs=4,
    )
    assert [r["id"] for r in summary["results"]] == ["a", "b", "c", "d"]
    assert summary["pulled"] == 4


def test_buildout_pull_search_enumeration() -> None:
    from openom_cli.buildout_pull import ids_from_search_result

    assert ids_from_search_result([1, 2, 3]) == ["1", "2", "3"]
    assert ids_from_search_result({"listings": [{"id": 7}, {"listing_id": 8}]}) == ["7", "8"]
    assert ids_from_search_result({"results": [{"ref": "x"}, {"ref": "x"}]}) == ["x"]  # de-duped
    assert ids_from_search_result({"nope": 1}) == []


def test_buildout_pull_mcp_parsing() -> None:
    # The MCP wire-format helpers (JSON + SSE + text-block + structuredContent).
    from openom_cli.buildout_pull import listing_from_result, parse_rpc

    j = parse_rpc("application/json", json.dumps({"result": {"structuredContent": {"a": 1}}}))
    assert listing_from_result(j) == {"a": 1}

    sse = "event: message\ndata: " + json.dumps(
        {"result": {"content": [{"type": "text", "text": json.dumps({"b": 2})}]}}
    ) + "\n\n"
    assert listing_from_result(parse_rpc("text/event-stream", sse)) == {"b": 2}

    err = {"error": {"code": -32000, "message": "nope"}}
    try:
        listing_from_result(err)
        raise AssertionError("expected error")
    except RuntimeError as e:
        assert "nope" in str(e)


def test_buildout_pull_cli_needs_ids(tmp_path: Path) -> None:
    r = runner.invoke(app, ["buildout-pull", "--endpoint", "https://mcp.example/mcp",
                            "--out-dir", str(tmp_path / "o")])
    assert r.exit_code == 2, r.output


def test_mirror_bytes_hash_equals_embedded_payload_hash(tmp_path: Path) -> None:
    # [M2] the JSON-LD mirror is the exact canonical preimage: its byte hash == the embedded
    # payloadHash, which is precisely what the domain-origin badge checks.
    from openom_core.canonical import hash_bytes

    base = _base_pdf(tmp_path / "base.pdf")
    stnl = SPEC / "samples" / "valid-stnl.json"
    out = tmp_path / "out.pdf"
    e = runner.invoke(app, ["embed", str(base), "--payload", str(stnl), "--out", str(out),
                            "--asserted-date", "2026-08-16", "--mirror"])
    assert e.exit_code == 0, e.output
    mirror_path = out.with_suffix(".jsonld")
    assert mirror_path.exists()  # embed --mirror wrote the sidecar

    # The embedded payloadHash (from read) equals hash of the mirror bytes.
    rr = json.loads(runner.invoke(app, ["read", str(out)]).output)
    # om read omits payloadHash; recompute from the mirror + compare to a standalone mirror.
    m = runner.invoke(app, ["mirror", str(out), "--out", str(tmp_path / "m2.jsonld")])
    assert m.exit_code == 0, m.output
    assert (tmp_path / "m2.jsonld").read_bytes() == mirror_path.read_bytes()  # deterministic
    # The mirror hash matches the payload the PDF carries.
    from openom_core.canonical import canonicalize
    assert hash_bytes(mirror_path.read_bytes()) == hash_bytes(canonicalize(rr["payload"]))


def test_mirror_from_payload_json(tmp_path: Path) -> None:
    stnl = SPEC / "samples" / "valid-stnl.json"
    m = runner.invoke(app, ["mirror", str(stnl), "--out", str(tmp_path / "p.jsonld")])
    assert m.exit_code == 0, m.output
    from openom_core.canonical import canonicalize
    expected = canonicalize(json.loads(stnl.read_text(encoding="utf-8")))
    assert (tmp_path / "p.jsonld").read_bytes() == expected


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


def test_validate_non_finite_flags_and_emits_valid_json(tmp_path: Path) -> None:
    # A non-finite number: validate must flag it (OMV-E011, matching embed) AND the output must
    # be RFC-8259-valid JSON - never a bare Infinity/NaN token an /js JSON.parse would reject.
    sample = json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))
    sample["deal"]["noi"] = float("inf")
    p = tmp_path / "inf.json"
    p.write_text(json.dumps(sample), encoding="utf-8")  # Python emits bare `Infinity` (lenient)
    r = runner.invoke(app, ["validate", str(p), "--schema", str(SPEC / "om-0.1.schema.json")])
    assert r.exit_code == 1
    assert "OMV-E011" in r.output
    assert "Infinity" not in r.output and "NaN" not in r.output  # no bare non-finite tokens
    # The JSON object on stdout parses (coaching goes to stderr, merged after the JSON).
    body = r.output[r.output.index("{") :]
    obj, _ = json.JSONDecoder().raw_decode(body)
    assert any(e["code"] == "OMV-E011" for e in obj["errors"])


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


def test_format_compact_is_single_line(tmp_path: Path) -> None:
    sample = str(SPEC / "samples" / "valid-stnl.json")
    r = runner.invoke(app, ["--format", "compact", "check", sample])
    assert r.exit_code == 0, r.output
    assert r.output.strip().count("\n") == 0  # one compact JSON line
    assert json.loads(r.output)["ok"] is True


def test_quiet_suppresses_stdout(tmp_path: Path) -> None:
    r = runner.invoke(app, ["--quiet", "check", str(SPEC / "samples" / "valid-stnl.json")])
    assert r.exit_code == 0
    assert r.stdout.strip() == ""  # nothing on stdout; exit code carries the result


def test_bad_format_is_usage_error(tmp_path: Path) -> None:
    r = runner.invoke(app, ["--format", "yaml", "read", "whatever.pdf"])
    assert r.exit_code == 2


def test_stdin_json_to_check(tmp_path: Path) -> None:
    payload = (SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8")
    r = runner.invoke(app, ["check", "-"], input=payload)
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["source"]["kind"] == "payload"


def test_embed_stdout_pipe_to_read(tmp_path: Path) -> None:
    base = _base_pdf(tmp_path / "base.pdf")
    sample = SPEC / "samples" / "valid-stnl.json"
    # embed to stdout (binary), then read those bytes back via stdin.
    r1 = runner.invoke(
        app,
        ["embed", str(base), "--payload", str(sample), "--out", "-",
         "--asserted-date", "2026-08-15"],
    )
    assert r1.exit_code == 0, r1.output
    embedded = r1.stdout_bytes
    assert embedded[:5] == b"%PDF-"
    r2 = runner.invoke(app, ["read", "-"], input=embedded)
    assert r2.exit_code == 0, r2.output
    assert json.loads(r2.output)["present"] is True


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


def test_force_utf8_switches_a_legacy_encoding() -> None:
    """#18: a cp1252 console stream is reconfigured to UTF-8 so em-dashes never mojibake."""
    from openom_cli.main import _force_utf8

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    _force_utf8(stream)
    assert stream.encoding == "utf-8"
    stream.write("em-dash - and middot ·")  # would raise on a strict cp1252 stream
    stream.flush()


def test_force_utf8_tolerates_a_non_reconfigurable_stream() -> None:
    """A test harness / pipe may swap stdout for a plain object w/o reconfigure - never raise."""
    from openom_cli.main import _force_utf8

    class _Plain:
        pass

    _force_utf8(_Plain())  # no exception


def test_help_renders_non_ascii_without_error() -> None:
    """The app help (em-dash) is emitted cleanly through the runner."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "-" in result.stdout


def test_watch_once_embeds_pairs_and_skips_lonely_pdf(tmp_path: Path) -> None:
    """#17: watch --once embeds each <name>.pdf that has a sibling <name>.json; a PDF without
    a JSON is left for later, and the produced OM reads back."""
    import shutil

    indir = tmp_path / "in"
    outdir = tmp_path / "out"
    indir.mkdir()
    _base_pdf(indir / "deal.pdf")
    shutil.copyfile(SPEC / "samples" / "valid-stnl.json", indir / "deal.json")
    _base_pdf(indir / "lonely.pdf")  # no lonely.json → must be skipped silently

    result = runner.invoke(
        app, ["watch", str(indir), "--out", str(outdir), "--asserted-date", "2026-08-18", "--once"]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    names = {e["name"]: e for e in payload["events"]}
    assert names["deal"]["action"] == "embedded"
    assert "lonely" not in names  # incomplete pair not processed
    produced = outdir / "deal.openom.pdf"
    assert produced.is_file()
    read = runner.invoke(app, ["read", str(produced)])
    assert json.loads(read.stdout)["present"] is True


def test_watch_once_skips_schema_invalid_payload(tmp_path: Path) -> None:
    """A payload with schema errors is skipped (never embedded) when --schema is given."""
    indir = tmp_path / "in"
    outdir = tmp_path / "out"
    indir.mkdir()
    _base_pdf(indir / "bad.pdf")
    # missing required fields → schema errors
    (indir / "bad.json").write_text('{"@type": "RealEstateListing"}', encoding="utf-8")

    result = runner.invoke(
        app,
        ["watch", str(indir), "--out", str(outdir), "--asserted-date", "2026-08-18",
         "--schema", str(SPEC / "om-0.1.schema.json"), "--once"],
    )
    assert result.exit_code == 0, result.stdout
    ev = json.loads(result.stdout)["events"][0]
    assert ev["action"] == "skipped" and ev["reason"] == "schema-errors"
    assert not (outdir / "bad.openom.pdf").exists()
