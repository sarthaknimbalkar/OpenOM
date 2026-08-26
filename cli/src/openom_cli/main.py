# SPDX-License-Identifier: MIT
"""The ``om`` CLI over openom-core (spec §5a). Thin, deterministic, zero inference.

Commands: embed · embed-batch · buildout-pull · buildout-manifest · mirror · read · inspect ·
validate · check · extract · conformance · version. JSON goes
to stdout (``--format pretty|compact``; ``--quiet`` suppresses it). A path of ``-`` means stdin
(input) or stdout (``embed --out -``) for pipe-friendly use. Exit codes: 0 ok · 1 validation/
conformance failure · 2 usage (typer) · 3 data/IO error (bad PDF/JSON, OM-IO-*). Warnings never
affect the exit code.
"""

from __future__ import annotations

import csv
import dataclasses
import datetime
import functools
import io
import json
import sys
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Annotated, Any, TypeVar, cast

import pikepdf
import typer
from openom_core import SPEC_VERSION
from openom_core.canonical import canonicalize, hash_bytes
from openom_core.canonical import parse_hardened as _parse_hardened
from openom_core.embed import embed as _embed
from openom_core.embed import input_encrypted as _input_encrypted
from openom_core.embed import read as _read
from openom_core.embed import reembed_warnings as _reembed_warnings
from openom_core.errors import CanonicalizationError, PayloadTooLargeError, SignedEmbedError
from openom_core.images import extract_images as _extract_images
from openom_core.inspect import inspect as _inspect
from openom_core.text import extract_text as _extract_text
from openom_core.validate import validate as _validate

from openom_cli import profile as _profile
from openom_cli import scaffold as _scaffold
from openom_cli.buildout import listing_to_payload, payload_coverage
from openom_cli.csv_map import CANONICAL_COLUMNS, override_identity, row_to_payload, template_csv
from openom_cli.humanize import footer as _err_footer
from openom_cli.humanize import humanize_finding as _humanize


def _force_utf8(stream: object) -> None:
    """Emit UTF-8 on a text stream regardless of the OS console codepage (#18).

    On Windows with a legacy codepage (cp1252) - the default on Python < 3.15 or under
    ``PYTHONUTF8=0`` - the em-dashes / middots in help text and any non-ASCII in JSON output
    mojibake or raise UnicodeEncodeError. Reconfiguring to UTF-8 fixes it everywhere. Text layer
    only: the binary ``embed --out -`` path writes ``sys.stdout.buffer`` and is unaffected.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return  # e.g. a test harness replaced stdout with a plain object
    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError):  # detached / already-written stream - best-effort
        pass


for _std in (sys.stdout, sys.stderr):
    _force_utf8(_std)

app = typer.Typer(
    help=(
        "openOM - embed broker-asserted, hash-verified deal data into your OM PDF (and read it "
        "back). Deterministic, zero AI, nothing leaves your machine.\n\n"
        "NOT A DEVELOPER? You don't need this terminal. If you just have an OM PDF and want to "
        "embed your deal, do it in your browser - no install, bytes never leave your device: "
        "https://openom.app/embed/\n\n"
        "Using the CLI? Start here:\n"
        "  om init                 # writes a ready-to-edit deal.json (no more 'no deal.json')\n"
        "  om profile set ...      # save your name/brokerage/license once - never retype it\n"
        "  om validate deal.json   # plain-English check before you embed\n"
        "  om embed listing.pdf --payload deal.json --out out.pdf --asserted-date <today>\n\n"
        "Global options (--format, --quiet, --version) go BEFORE the command."
    )
)

_F = TypeVar("_F", bound=Callable[..., Any])
_DATA_ERRORS = (
    CanonicalizationError,
    PayloadTooLargeError,
    SignedEmbedError,
    json.JSONDecodeError,
    pikepdf.PdfError,
    FileNotFoundError,
    UnicodeDecodeError,
)


def _guard(fn: _F) -> _F:
    """Turn expected data/IO failures into a clean stderr message + exit 3 (never a traceback)."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except typer.Exit:
            raise
        except _DATA_ERRORS as exc:
            code = getattr(exc, "code", None)
            typer.echo(f"error: {f'{code}: ' if code else ''}{exc}", err=True)
            raise typer.Exit(3) from exc

    return cast("_F", wrapper)


@dataclasses.dataclass
class _Output:
    """Global output state set by the top-level callback (--format / --quiet)."""

    fmt: str = "pretty"
    quiet: bool = False


_output = _Output()


def _tool_version() -> str:
    try:
        return _pkg_version("openom-cli")
    except PackageNotFoundError:  # pragma: no cover - source tree
        return "0.0.0-dev"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"openom-cli {_tool_version()} (spec {SPEC_VERSION})")
        raise typer.Exit(0)


@app.callback()
def _main(
    output_format: Annotated[
        str, typer.Option("--format", help="stdout JSON format: pretty | compact")
    ] = "pretty",
    quiet: Annotated[
        bool, typer.Option("--quiet", help="Suppress stdout (exit code + stderr only)")
    ] = False,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Print the tool + spec version and exit.",
            is_eager=True,
            callback=_version_callback,
        ),
    ] = False,
) -> None:
    """openOM CLI. NOTE: global options (--format, --quiet, --version) go BEFORE the command,
    e.g. `om --format compact read x.pdf`."""
    if output_format not in ("pretty", "compact"):
        typer.echo(f"error: --format must be pretty|compact, got {output_format!r}", err=True)
        raise typer.Exit(2)
    _output.fmt = output_format
    _output.quiet = quiet


def _read_bytes(path: Path) -> bytes:
    """Read a file, or stdin when the path is ``-`` (binary-safe, for piping)."""
    return sys.stdin.buffer.read() if str(path) == "-" else path.read_bytes()


def _write_bytes(path: Path, data: bytes) -> None:
    """Write a file, or stdout when the path is ``-`` (binary-safe)."""
    if str(path) == "-":
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    else:
        path.write_bytes(data)


def _gitignored(path: Path) -> bool:
    """True if `path` is already ignored (a cheap check so `om init` doesn't nag redundantly)."""
    try:
        import subprocess

        r = subprocess.run(
            ["git", "check-ignore", "-q", str(path)], capture_output=True, timeout=3
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _load_json(path: Path) -> dict[str, Any]:
    # parse_hardened enforces the same §J read invariants the embed/MCP paths do - reject duplicate
    # keys and over-deep nesting - degrading a pathological payload to a structured OM-IO error
    # (caught by _guard -> exit 3) instead of a RecursionError traceback.
    text = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    return cast("dict[str, Any]", _parse_hardened(text))


def _emit(obj: Any) -> None:
    if _output.quiet:
        return
    # allow_nan=False: never emit bare Infinity/NaN tokens (invalid per RFC 8259; an /js
    # JSON.parse rejects them). A non-finite leaf is a data error, not silently serialized as JSON.
    if _output.fmt == "compact":
        typer.echo(
            json.dumps(obj, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        )
    else:
        typer.echo(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False))


def _echo_human_errors(errors: list[Any]) -> None:
    """Plain-English error coaching to stderr; stdout keeps the JSON contract (--quiet mutes)."""
    if not errors or _output.quiet:
        return
    for f in errors:
        typer.echo(_humanize(f.code, f.path, f.message), err=True)
    typer.echo(_err_footer(), err=True)


def _echo_embed_usage() -> None:
    """The friendly stand-in for typer's bare 'Missing option' - what to do + the browser escape."""
    typer.echo(
        "error: `embed` needs the OM PDF, the deal data, an output path, and an assertion date.\n"
        "  Don't have a deal file yet?  om init            # writes a ready-to-edit deal.json\n"
        "  Then:  om embed listing.pdf --payload deal.json --out listing.openom.pdf "
        "--asserted-date <today>\n"
        "  Just have a PDF and you're not a developer? Skip the terminal - embed in your browser "
        "(nothing leaves your machine): https://openom.app/embed/",
        err=True,
    )


def _require_input_pdf(pdf: Path) -> None:
    if str(pdf) == "-" or pdf.exists():
        return
    typer.echo(f"error: input PDF not found: {pdf}. Check the path and try again.", err=True)
    raise typer.Exit(3)


def _require_payload(payload: Path) -> None:
    if str(payload) == "-" or payload.exists():
        return
    typer.echo(
        f"error: payload file not found: {payload} - this is the deal data to embed, and it "
        f"doesn't exist yet. Create it first:  om init {payload}  (writes a ready-to-edit "
        f"template), edit the values, then re-run. Not a developer with just a PDF? Embed in your "
        f"browser instead: https://openom.app/embed/",
        err=True,
    )
    raise typer.Exit(3)


@app.command()
@_guard
def embed(
    pdf: Annotated[Path | None, typer.Argument(help="Input OM PDF (required)")] = None,
    payload: Annotated[
        Path | None,
        typer.Option(help="Deal-data JSON to embed (required; create one with `om init`)"),
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Output PDF path (required)")] = None,
    asserted_date: Annotated[
        str | None,
        typer.Option(
            "--asserted-date", "--date",  # --date is the flag a broker reaches for first
            help="ISO 8601 assertion date (required), e.g. 2026-08-24",
        ),
    ] = None,
    mirror: Annotated[
        bool,
        typer.Option(
            help="Also write the JSON-LD web mirror (<out>.jsonld) - the exact bytes the "
            "domain-origin badge verifies against ([M2])"
        ),
    ] = False,
    validate: Annotated[
        bool,
        typer.Option(
            "--validate/--no-validate",
            help="Validate the payload against the 0.1 schema first and REFUSE (exit 1) on schema "
            "errors (ON by default, matching the browser author gate and Rule 6). Pass "
            "--no-validate only to embed a deliberate draft.",
        ),
    ] = True,
) -> None:
    """Embed deal data into an OM PDF. Validates first by default and refuses a schema-invalid
    payload (use --no-validate to override). Not a developer with just a PDF? Skip the terminal -
    embed in your browser (nothing leaves your machine): https://openom.app/embed/"""
    if pdf is None or payload is None or out is None or asserted_date is None:
        _echo_embed_usage()
        raise typer.Exit(2)
    _require_input_pdf(pdf)
    _require_payload(payload)
    src = _read_bytes(pdf)
    data = _load_json(payload)
    if _input_encrypted(src) and not _output.quiet:
        typer.echo(
            "warning: this OM is permission-encrypted; the embedded copy will be UNENCRYPTED "
            "(open/print/copy restrictions removed). Keep the original if you need those.",
            err=True,
        )
    if _profile.merge_into(data) and not _output.quiet:
        typer.echo("note: filled assertedBy from your saved profile (`om profile show`)", err=True)
    if validate:
        report = _validate(data)  # defaults to the bundled 0.1 schema
        if report.errors:
            for f in report.errors:
                typer.echo(_humanize(f.code, f.path, f.message), err=True)
            typer.echo(_err_footer(), err=True)
            raise typer.Exit(1)
    for w in _reembed_warnings(src, data, asserted_date=asserted_date):
        typer.echo(f"warning {w.code} {w.path}: {w.message}", err=True)
    embedded = _embed(src, data, asserted_date=asserted_date)
    _write_bytes(out, embedded)
    if mirror and str(out) == "-":
        typer.echo("warning: --mirror ignored with `--out -` (stdout); pass a file path", err=True)
    if mirror and str(out) != "-":
        mpath = out.with_suffix(".jsonld")
        # The mirror MUST be the canonical (JCS) preimage bytes so its hash == the embedded
        # payloadHash; read the payload back from the PDF so it reflects exactly what was stamped.
        mpath.write_bytes(canonicalize(_read(embedded).payload or data))
        if not _output.quiet:
            typer.echo(f"wrote web mirror -> {mpath}", err=True)
    # Status to stderr so `--out -` keeps a clean binary PDF on stdout for piping.
    if not _output.quiet:
        typer.echo(f"embedded om.json -> {'<stdout>' if str(out) == '-' else out}", err=True)


@app.command()
@_guard
def init(
    out: Annotated[Path, typer.Argument(help="Where to write the starter payload")] = Path(
        "deal.json"
    ),
    template: Annotated[
        str, typer.Option(help="Which shape to start from: stnl | multifamily | proforma")
    ] = "stnl",
    force: Annotated[bool, typer.Option(help="Overwrite an existing file")] = False,
) -> None:
    """Write a ready-to-edit starter deal.json, so 'no deal.json' can never happen.

    The file is schema-valid EXAMPLE data - swap in your deal's numbers, then `om embed`. Your saved
    broker profile (`om profile set`) fills assertedBy automatically."""
    if template not in _scaffold.TEMPLATES:
        typer.echo(
            f"error: unknown template {template!r} - choose one of: "
            f"{', '.join(_scaffold.TEMPLATES)}",
            err=True,
        )
        raise typer.Exit(2)
    if out.exists() and not force:
        typer.echo(
            f"error: {out} already exists - pass --force to overwrite, or `om init my-deal.json`",
            err=True,
        )
        raise typer.Exit(3)
    saved = _profile.profile_asserted_by()
    doc = _scaffold.build_skeleton(
        template, today=datetime.date.today().isoformat(), profile_asserted_by=saved
    )
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not _output.quiet:
        for line in _scaffold.guidance_lines(template, str(out), has_profile=bool(saved)):
            typer.echo(line, err=True)
        # If this is a git repo, nudge the broker not to commit their draft deal data by accident.
        if Path(".git").is_dir() and not _gitignored(out):
            typer.echo(
                f"tip: {out} holds your draft deal data - add it to .gitignore so it isn't "
                "committed by accident.",
                err=True,
            )


profile_app = typer.Typer(help="Save your broker identity once so you never retype it.")
app.add_typer(profile_app, name="profile")


@profile_app.command("set")
def profile_set(
    broker: Annotated[str | None, typer.Option(help='Your name, e.g. "Jane Broker"')] = None,
    brokerage: Annotated[str | None, typer.Option(help="Your brokerage")] = None,
    license: Annotated[
        str | None, typer.Option(help='Your license id, e.g. "MI 6501-000000"')
    ] = None,
) -> None:
    """Save your name / brokerage / license to this device; `om init` and `om embed` reuse them."""
    if broker is None and brokerage is None and license is None:
        typer.echo(
            "nothing to set - pass --broker/--brokerage/--license, e.g.\n"
            '  om profile set --broker "Jane Broker" --brokerage "Acme" --license "MI 6501-000000"',
            err=True,
        )
        raise typer.Exit(2)
    prof = _profile.save_profile(broker=broker, brokerage=brokerage, license=license)
    ab = prof["assertedBy"]
    typer.echo(
        f"Saved your broker profile -> {_profile.profile_path()} "
        "(on this device; you won't retype it)",
        err=True,
    )
    for key in ("broker", "brokerage", "license"):
        if ab.get(key):
            typer.echo(f"  {key + ':':11}{ab[key]}", err=True)
    typer.echo("`om init` and `om embed` will fill assertedBy from this automatically.", err=True)


@profile_app.command("show")
def profile_show() -> None:
    """Print your saved broker profile (or how to set one)."""
    prof = _profile.load_profile()
    if not prof.get("assertedBy"):
        typer.echo(
            "No profile saved yet. Set one so you never retype it:\n"
            '  om profile set --broker "Your Name" --brokerage "Your Co" --license "..."',
            err=True,
        )
        return
    _emit(prof)


@profile_app.command("path")
def profile_path_cmd() -> None:
    """Print the file where your profile is stored (edit it directly if you like)."""
    typer.echo(str(_profile.profile_path()))


def _embed_one(task: dict[str, Any]) -> dict[str, Any]:
    """Process one batch item. Top-level + picklable so it runs in a worker process (--jobs). Pure
    given resolved paths; re-imports the core so ProcessPoolExecutor spawn works everywhere."""
    from openom_core.embed import embed as _e
    from openom_core.embed import reembed_warnings as _rw
    from openom_core.validate import validate as _v

    rec: dict[str, Any] = {"index": task["index"], "pdf": task["pdf"], "out": task["out"]}
    try:
        payload = json.loads(Path(task["payload"]).read_text(encoding="utf-8"))
        date = task["date"]
        report = _v(payload, schema=task["schema"], as_of=date)
        rec["warnings"] = [f.code for f in report.warnings]
        if not report.ok:  # schema errors block this item (Rule 6)
            rec["status"] = "skipped"
            rec["errors"] = [f"{f.code}: {f.path}" for f in report.errors]
            return rec
        src = Path(task["pdf"]).read_bytes()
        # supersedes / backwards-date notes surfaced per item
        rec["reembed"] = [w.code for w in _rw(src, payload, asserted_date=date)]
        out = Path(task["out"])
        if out.exists() and task["skip_existing"]:
            rec["status"] = "skipped-existing"
            return rec
        if out.exists() and not task["force"]:
            rec["status"] = "error"
            rec["errors"] = ["output exists (use --force, or --skip-existing to resume)"]
            return rec
        if task["dry_run"]:
            rec["status"] = "would-embed"
            return rec
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(_e(src, payload, asserted_date=date))
        rec["status"] = "embedded"
    except Exception as e:  # one bad item never aborts the batch  # noqa: BLE001
        rec["status"] = "error"
        rec.setdefault("errors", []).append(str(e))
    return rec


@app.command(name="embed-batch")
@_guard
def embed_batch(  # noqa: C901 - a linear orchestrator (resolve -> dispatch -> report), read top-down
    manifest: Annotated[
        Path | None, typer.Option(help="JSON array of {pdf, payload, out?, assertedDate?} items")
    ] = None,
    dir: Annotated[  # noqa: A002 - the user-facing flag name
        Path | None,
        typer.Option(help="Directory of *.pdf, each paired with a sibling *.om.json (or *.json)"),
    ] = None,
    out_dir: Annotated[
        Path, typer.Option(help="Output dir for items without an explicit 'out'")
    ] = Path("openom-out"),
    asserted_date: Annotated[
        str | None, typer.Option(help="Default ISO 8601 assertion date for items without one")
    ] = None,
    schema: Annotated[
        Path | None, typer.Option(help="JSON Schema; schema-invalid payloads are skipped")
    ] = None,
    dry_run: Annotated[bool, typer.Option(help="Validate + report only; write nothing")] = False,
    skip_existing: Annotated[
        bool, typer.Option(help="Skip items whose output already exists (resume a large run)")
    ] = False,
    force: Annotated[bool, typer.Option(help="Overwrite existing outputs")] = False,
    jobs: Annotated[int, typer.Option(help="Parallel workers (processes) for large catalogs")] = 1,
    report: Annotated[Path | None, typer.Option(help="Write the JSON summary to this file")] = None,
) -> None:
    """Embed openOM payloads into many OMs in one run - back-catalog seeding (adoption).

    Source the batch from a --manifest (JSON array; paths relative to the manifest) OR a --dir of
    PDFs each with a sibling <name>.om.json payload. Deterministic, non-destructive, idempotent
    (re-embed replaces + records ``supersedes``; those notes are surfaced per item). Schema errors
    skip that item (Rule 6); consistency warnings never block. --dry-run previews, --skip-existing
    resumes, --jobs parallelizes. Emits a JSON summary (counts + per-item results); exits non-zero
    if any item errored or was schema-skipped.
    """
    if bool(manifest) == bool(dir):
        typer.echo("error: pass exactly one of --manifest or --dir", err=True)
        raise typer.Exit(2)
    if dir:
        base = dir.resolve()
        raw_items: list[dict[str, Any]] = []
        for p in sorted(base.glob("*.pdf")):
            names = (f"{p.stem}.om.json", f"{p.stem}.json")
            sidecar = next((s for s in names if (base / s).exists()), None)
            raw_items.append({"pdf": p.name, "payload": sidecar} if sidecar else {"pdf": p.name})
    else:
        assert manifest is not None
        loaded = json.loads(_read_bytes(manifest).decode("utf-8"))
        if not isinstance(loaded, list):
            typer.echo("error: OM-IO manifest must be a JSON array", err=True)
            raise typer.Exit(3)
        raw_items = loaded
        base = manifest.resolve().parent

    schema_obj = _load_json(schema) if schema is not None else None
    tasks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []  # normalization failures, kept out of the worker pool
    seen_out: dict[str, int] = {}
    for i, item in enumerate(raw_items):
        try:
            if not isinstance(item, dict) or not item.get("pdf") or not item.get("payload"):
                raise ValueError("item needs 'pdf' and a resolvable 'payload' (sidecar missing?)")
            pdf_path = (base / str(item["pdf"])).resolve()
            date = str(item.get("assertedDate") or asserted_date or "")
            if not date:
                raise ValueError("no assertedDate (set it on the item or pass --asserted-date)")
            out_path = (
                (base / str(item["out"])).resolve()
                if item.get("out")
                else (out_dir.resolve() / f"{pdf_path.stem}.pdf")
            )
            if out_path == pdf_path:
                raise ValueError("output would overwrite the input PDF")
            if str(out_path) in seen_out:
                raise ValueError(f"two items target the same output ({out_path})")
            seen_out[str(out_path)] = i
            tasks.append({
                "index": i, "pdf": str(pdf_path),
                "payload": str((base / str(item["payload"])).resolve()),
                "out": str(out_path), "date": date, "schema": schema_obj,
                "dry_run": dry_run, "skip_existing": skip_existing, "force": force,
            })
        except Exception as e:  # noqa: BLE001
            errors.append({"index": i, "pdf": str(item.get("pdf", "?")),
                           "status": "error", "errors": [str(e)]})

    if jobs > 1 and len(tasks) > 1 and not dry_run:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            done = list(ex.map(_embed_one, tasks))
    else:
        done = [_embed_one(t) for t in tasks]

    results = sorted([*errors, *done], key=lambda r: r["index"])
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    summary = {"total": len(results), "counts": counts, "dryRun": dry_run, "results": results}
    if report is not None:
        report.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if not _output.quiet:
        ok = counts.get("embedded", 0) + counts.get("would-embed", 0)
        tally = " ".join(f"{k}={v}" for k, v in counts.items())
        typer.echo(f"embed-batch: {ok}/{len(results)} ok - {tally}", err=True)
    _emit(summary)
    failed = counts.get("error", 0) + counts.get("skipped", 0)
    raise typer.Exit(code=1 if failed else 0)


@app.command(name="buildout-manifest")
@_guard
def buildout_manifest(
    listings_dir: Annotated[
        Path, typer.Option(help="Dir of Buildout get_listing JSON files (named <id>.json)")
    ],
    pdf_dir: Annotated[
        Path, typer.Option(help="Dir with the OM PDFs (named <id>.pdf) for those listings")
    ],
    out_dir: Annotated[
        Path, typer.Option(help="Where payload sidecars + manifest.json are written")
    ],
    broker: Annotated[str, typer.Option(help="assertedBy.broker (who is asserting)")],
    brokerage: Annotated[str, typer.Option(help="assertedBy.brokerage")],
    license: Annotated[str, typer.Option(help="assertedBy.license")],  # noqa: A002
    asserted_date: Annotated[str, typer.Option(help="ISO 8601 assertion date")],
    noi_type: Annotated[str, typer.Option(help="in-place | pro-forma (a required assertion)")],
    noi_as_of: Annotated[
        str | None, typer.Option(help="deal.noiAsOfDate (default: --asserted-date)")
    ] = None,
    overrides: Annotated[
        Path | None,
        typer.Option(
            help="JSON {listing-id: {broker,brokerage,license,noiType,noiAsOfDate}} - per-listing "
            "assertion identity overriding the flags (a catalog spans many brokers / NOI types)"
        ),
    ] = None,
    min_fields: Annotated[
        int, typer.Option(help="Flag any mapped payload with fewer than this many tracked fields")
    ] = 3,
) -> None:
    """Bridge: turn fetched Buildout listings into an ``om embed-batch`` manifest (catalog seed).

    Deterministic, zero inference: each get_listing JSON is mapped to a schema-valid openOM payload
    (assertion identity from flags, or per-listing via ``--overrides``, never inferred), written
    as <id>.om.json, and paired with <id>.pdf in a manifest. A ``coverage.json`` reports each
    listing's filled/omitted fields so you can triage BEFORE a bulk embed (Rule 6: review at scale).
    Review/edit the payloads (the assertion gate), then run
    ``om embed-batch --manifest <out-dir>/manifest.json``. Listings with no OM PDF are skipped, each
    with a reason.
    """
    default_by = {"broker": broker, "brokerage": brokerage, "license": license}
    ov: dict[str, dict[str, str]] = (
        json.loads(overrides.read_text(encoding="utf-8")) if overrides else {}
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    coverage: list[dict[str, Any]] = []
    sparse: list[str] = []
    for jf in sorted(listings_dir.glob("*.json")):
        stem = jf.stem
        listing = json.loads(jf.read_text(encoding="utf-8"))
        pdf = pdf_dir / f"{stem}.pdf"
        if not pdf.exists():
            skipped.append({"id": stem, "reason": f"no OM PDF at {pdf.name}"})
            continue
        row = ov.get(stem, {})
        asserted_by = {
            "broker": row.get("broker", default_by["broker"]),
            "brokerage": row.get("brokerage", default_by["brokerage"]),
            "license": row.get("license", default_by["license"]),
        }
        payload = listing_to_payload(
            listing, asserted_by=asserted_by, asserted_date=asserted_date,
            noi_type=row.get("noiType", noi_type),
            noi_as_of=row.get("noiAsOfDate", noi_as_of),
        )
        sidecar = out_dir / f"{stem}.om.json"
        sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest.append(
            {"pdf": str(pdf.resolve()), "payload": str(sidecar.resolve()),
             "assertedDate": asserted_date}
        )
        cov = payload_coverage(payload)
        coverage.append({"id": stem, **cov})
        if cov["filled"] < min_fields:
            sparse.append(stem)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "coverage.json").write_text(
        json.dumps({"listings": coverage, "sparse": sparse, "minFields": min_fields}, indent=2),
        encoding="utf-8",
    )
    if not _output.quiet:
        note = f", {len(sparse)} sparse (<{min_fields} fields)" if sparse else ""
        typer.echo(
            f"buildout-manifest: {len(manifest)} mapped, {len(skipped)} skipped{note} -> {out_dir}",
            err=True,
        )
    _emit({
        "mapped": len(manifest), "skipped": skipped, "sparse": sparse,
        "manifest": str(out_dir / "manifest.json"), "coverage": str(out_dir / "coverage.json"),
    })


@app.command(name="csv-manifest")
@_guard
def csv_manifest(  # noqa: C901 - a linear map-each-row-then-report, read top-down
    csv_file: Annotated[
        Path | None, typer.Option("--csv", help="Spreadsheet of listings (canonical columns)")
    ] = None,
    pdf_dir: Annotated[
        Path | None, typer.Option(help="Dir of the OM PDFs (named per each row's id/pdf column)")
    ] = None,
    out_dir: Annotated[
        Path | None, typer.Option(help="Where payload sidecars + manifest.json are written")
    ] = None,
    broker: Annotated[str | None, typer.Option(help="assertedBy.broker (who is asserting)")] = None,
    brokerage: Annotated[str | None, typer.Option(help="assertedBy.brokerage")] = None,
    license: Annotated[str | None, typer.Option(help="assertedBy.license")] = None,  # noqa: A002
    asserted_date: Annotated[
        str | None, typer.Option(help="ISO 8601 assertion date")
    ] = None,
    noi_type: Annotated[
        str | None, typer.Option(help="in-place | pro-forma (a required assertion)")
    ] = None,
    noi_as_of: Annotated[
        str | None, typer.Option(help="deal.noiAsOfDate (default: --asserted-date)")
    ] = None,
    min_fields: Annotated[
        int, typer.Option(help="Flag any mapped payload with fewer than this many tracked fields")
    ] = 3,
    template: Annotated[
        Path | None,
        typer.Option(help="Write a blank template CSV (headers + one example) here, then exit"),
    ] = None,
) -> None:
    """Bridge: turn a broker's spreadsheet into an ``om embed-batch`` manifest (catalog seed).

    The low-touch on-ramp: a broker exports their back catalog to a CSV (the canonical columns; run
    ``--template`` to get a blank one) and drops the OM PDFs in a folder. Each row maps
    deterministically (zero inference) to a schema-valid openOM payload written as ``<id>.om.json``,
    paired with its ``<id>.pdf`` in a manifest, with a ``coverage.json`` triage report. Assertion
    identity comes from the flags (or per-row ``broker``/``brokerage``/``license``/``noiType``
    columns for a multi-broker catalog), stamped verbatim - never inferred. Review the payloads (the
    assertion gate), then run ``om embed-batch --manifest <out-dir>/manifest.json``.
    """
    if template is not None:
        template.write_text(template_csv(), encoding="utf-8")
        if not _output.quiet:
            typer.echo(f"csv-manifest: wrote a template with {len(CANONICAL_COLUMNS)} columns "
                       f"-> {template}", err=True)
        _emit({"template": str(template), "columns": list(CANONICAL_COLUMNS)})
        return

    missing = [
        n for n, v in (
            ("--csv", csv_file), ("--pdf-dir", pdf_dir), ("--out-dir", out_dir),
            ("--broker", broker), ("--brokerage", brokerage), ("--license", license),
            ("--asserted-date", asserted_date), ("--noi-type", noi_type),
        ) if not v
    ]
    if missing:
        typer.echo(f"error: missing required option(s): {', '.join(missing)}", err=True)
        raise typer.Exit(2)
    # Narrow every required option to non-None for the type checker (the guard above proved it).
    assert csv_file and pdf_dir and out_dir and asserted_date
    assert broker and brokerage and license and noi_type

    default_by = {"broker": broker, "brokerage": brokerage, "license": license}
    rows = list(csv.DictReader(io.StringIO(_read_bytes(csv_file).decode("utf-8-sig"))))
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    coverage: list[dict[str, Any]] = []
    sparse: list[str] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        pdf_name = (row.get("pdf") or "").strip() or (
            f"{(row.get('id') or '').strip()}.pdf" if (row.get("id") or "").strip() else ""
        )
        stem = Path(pdf_name).stem if pdf_name else f"row{i + 1}"
        if not pdf_name:
            skipped.append({"id": stem, "reason": "row names no pdf (needs an 'id' or 'pdf')"})
            continue
        if stem in seen:
            skipped.append({"id": stem, "reason": "duplicate id/pdf in the CSV"})
            continue
        seen.add(stem)
        pdf = pdf_dir / pdf_name
        if not pdf.exists():
            skipped.append({"id": stem, "reason": f"no OM PDF at {pdf_name}"})
            continue
        ov = override_identity(row)
        asserted_by = {k: ov.get(k, default_by[k]) for k in ("broker", "brokerage", "license")}
        payload = row_to_payload(
            row, asserted_by=asserted_by, asserted_date=asserted_date,
            noi_type=ov.get("noiType", noi_type), noi_as_of=ov.get("noiAsOfDate", noi_as_of),
        )
        sidecar = out_dir / f"{stem}.om.json"
        sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest.append(
            {"pdf": str(pdf.resolve()), "payload": str(sidecar.resolve()),
             "assertedDate": asserted_date}
        )
        cov = payload_coverage(payload)
        coverage.append({"id": stem, **cov})
        if cov["filled"] < min_fields:
            sparse.append(stem)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "coverage.json").write_text(
        json.dumps({"listings": coverage, "sparse": sparse, "minFields": min_fields}, indent=2),
        encoding="utf-8",
    )
    if not _output.quiet:
        note = f", {len(sparse)} sparse (<{min_fields} fields)" if sparse else ""
        typer.echo(
            f"csv-manifest: {len(manifest)} mapped, {len(skipped)} skipped{note} -> {out_dir}",
            err=True,
        )
    _emit({
        "mapped": len(manifest), "skipped": skipped, "sparse": sparse,
        "manifest": str(out_dir / "manifest.json"), "coverage": str(out_dir / "coverage.json"),
    })


@app.command(name="buildout-pull")
@_guard
def buildout_pull(
    endpoint: Annotated[str, typer.Option(help="Buildout MCP Streamable-HTTP endpoint")],
    out_dir: Annotated[
        Path, typer.Option(help="Output dir; writes listings/<id>.json + pdfs/<id>.pdf")
    ],
    ids: Annotated[
        str | None, typer.Option(help="Comma-separated listing ids to pull")
    ] = None,
    ids_file: Annotated[
        Path | None, typer.Option(help="File of listing ids, one per line (alternative to --ids)")
    ] = None,
    search: Annotated[
        str | None,
        typer.Option(help="Enumerate ids via the search tool with this query (whole-catalog pull)"),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option(
            help="Bearer token (or set OPENOM_BUILDOUT_TOKEN)", envvar="OPENOM_BUILDOUT_TOKEN"
        ),
    ] = None,
    listing_tool: Annotated[
        str, typer.Option(help="MCP tool that returns a listing by ref")
    ] = "get_listing",
    search_tool: Annotated[
        str, typer.Option(help="MCP tool that searches/enumerates listings")
    ] = "search_listings",
    skip_existing: Annotated[
        bool, typer.Option(help="Skip listings already pulled (resume a run)")
    ] = False,
    jobs: Annotated[int, typer.Option(help="Concurrent downloads (I/O-bound)")] = 1,
    report: Annotated[
        Path | None, typer.Option(help="Write the JSON summary to this file")
    ] = None,
) -> None:
    """Pull a Buildout back-catalog: each listing + its OM PDF in one authenticated pass (#B3).

    Deterministic, zero inference (a data fetch). Writes ``listings/<id>.json`` + ``pdfs/<id>.pdf``,
    ready for ``om buildout-manifest --listings-dir <out>/listings --pdf-dir <out>/pdfs``. Give ids
    (``--ids``/``--ids-file``) or ``--search <query>`` to enumerate the whole catalog.
    ``--skip-existing`` resumes; ``--jobs`` downloads concurrently. Needs a Buildout MCP endpoint +
    token; listings with no discoverable OM PDF are recorded (``no-om``), the JSON still written.
    """
    from openom_cli.buildout_pull import (
        http_fetch_pdf,
        ids_from_search_result,
        mcp_http_call_tool,
        pull,
    )

    def get_listing(tool: str, args: dict[str, Any]) -> dict[str, Any]:
        return mcp_http_call_tool(endpoint, token, tool, args)

    id_list: list[str] = []
    if ids:
        id_list += [s.strip() for s in ids.split(",") if s.strip()]
    if ids_file:
        lines = ids_file.read_text(encoding="utf-8").splitlines()
        id_list += [ln.strip() for ln in lines if ln.strip()]
    if search:
        id_list += ids_from_search_result(get_listing(search_tool, {"query": search}))
    # de-dupe, preserve order
    id_list = list(dict.fromkeys(id_list))
    if not id_list:
        typer.echo("buildout-pull: no listing ids (use --ids, --ids-file, or --search)", err=True)
        raise typer.Exit(code=2)

    summary = pull(
        id_list,
        get_listing=get_listing,
        fetch_pdf=http_fetch_pdf,
        out_listings_dir=out_dir / "listings",
        out_pdf_dir=out_dir / "pdfs",
        listing_tool=listing_tool,
        skip_existing=skip_existing,
        jobs=jobs,
    )
    if report is not None:
        report.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if not _output.quiet:
        tally = " ".join(f"{k}={v}" for k, v in summary["counts"].items())
        typer.echo(
            f"buildout-pull: {summary['pulled']}/{summary['of']} pulled - {tally} -> {out_dir}",
            err=True,
        )
    _emit(summary)
    failed = sum(1 for r in summary["results"] if r["status"] in ("listing-error", "pdf-error"))
    raise typer.Exit(code=1 if failed else 0)


@app.command()
@_guard
def mirror(
    src: Annotated[Path, typer.Argument(help="An embedded openOM PDF, or a payload JSON")],
    out: Annotated[
        Path | None,
        typer.Option(help="Output .jsonld path (default: alongside the input; '-' for stdout)"),
    ] = None,
) -> None:
    """Emit the JSON-LD web mirror: the EXACT canonical (JCS) preimage bytes ([M2]).

    Host this next to a listing at a same-domain HTTPS URL and point the badge's ``mirror=`` at it;
    its byte hash equals the embedded ``payloadHash``, so the badge can show domain-origin.
    Reads the payload from an embedded PDF, or canonicalizes a payload JSON directly. Deterministic.
    """
    raw = _read_bytes(src)
    if raw[:5] == b"%PDF-" or (b"%PDF-" in raw[:1024]):
        payload = _read(raw).payload
        if payload is None:
            # [Mi11] "no embedded payload" is a data/IO condition -> exit 3, matching `check`
            # (was exit 1), so a script gets one consistent code for "not an openOM PDF".
            typer.echo("mirror: OM-IO-ABSENT: no openOM payload found in that PDF", err=True)
            raise typer.Exit(code=3)
    else:
        payload = json.loads(raw)
    bytes_out = canonicalize(payload)
    if out is not None and str(out) == "-":
        sys.stdout.buffer.write(bytes_out)
    else:
        dest = out if out is not None else src.with_suffix(".jsonld")
        dest.write_bytes(bytes_out)
        if not _output.quiet:
            typer.echo(f"wrote web mirror ({hash_bytes(bytes_out)}) -> {dest}", err=True)


@app.command()
@_guard
def read(pdf: Annotated[Path, typer.Argument(help="PDF to read")]) -> None:
    result = _read(_read_bytes(pdf))
    payload = result.payload or {}
    _emit(
        {
            "present": result.present,
            "payload": result.payload,
            "payloadHash": result.payload_hash,  # content hash - matches hosted om_read
            "sourceDocHash": result.source_doc_hash,  # #5: provenance of the underlying source PDF
            # The Rule 6 audit chain, first-class (no pikepdf / payload-digging needed):
            "assertedDate": payload.get("assertedDate"),
            "supersedes": (payload.get("meta") or {}).get("supersedes"),
            "verification": {
                "hashValid": result.hash_valid,
                "originVerified": result.origin_verified,
                "signatureValid": result.signature_valid,
            },
        }
    )


@app.command()
@_guard
def inspect(pdf: Annotated[Path, typer.Argument(help="PDF to inspect")]) -> None:
    _emit(_inspect(_read_bytes(pdf)))


@app.command()
@_guard
def validate(
    payload: Annotated[Path, typer.Argument(help="Payload JSON to validate")],
    schema: Annotated[Path | None, typer.Option(help="JSON Schema (enables error tier)")] = None,
) -> None:
    schema_obj = _load_json(schema) if schema is not None else None
    report = _validate(_load_json(payload), schema=schema_obj)
    _emit(
        {
            "errors": [dataclasses.asdict(f) for f in report.errors],
            "warnings": [dataclasses.asdict(f) for f in report.warnings],
            "info": [dataclasses.asdict(f) for f in report.info],
            "ok": report.ok,
        }
    )
    _echo_human_errors(report.errors)
    # Plain-English confirmation on success (to stderr; stdout keeps the JSON contract) - else a
    # non-technical broker sees only a wall of JSON exactly when everything passed.
    if report.ok and not _output.quiet:
        if report.warnings:
            typer.echo(
                f"Looks good - ready to embed. ({len(report.warnings)} advisory "
                f"{'warning' if len(report.warnings) == 1 else 'warnings'} to review):",
                err=True,
            )
            for w in report.warnings:
                typer.echo(f"  - {_humanize(w.code, w.path, w.message)}", err=True)
        else:
            typer.echo("Looks good - ready to embed.", err=True)
    raise typer.Exit(code=0 if report.ok else 1)


@app.command()
@_guard
def check(
    input: Annotated[
        Path, typer.Argument(help="A payload JSON file OR a PDF with an embedded om.json")
    ],
    schema: Annotated[
        Path | None, typer.Option(help="JSON Schema (enables the error tier)")
    ] = None,
    as_of: Annotated[
        str | None, typer.Option(help="Processing date (YYYY-MM-DD) for term/future checks")
    ] = None,
    strict: Annotated[
        bool, typer.Option(help="Exit non-zero on consistency warnings, not just schema errors")
    ] = False,
) -> None:
    """Standalone consistency check on a payload OR an embedded-PDF payload (§9 / M1.x).

    Runs the deterministic consistency tier with no network and no inference. Schema is optional:
    without it, only the internal-consistency (OMW-W###) + info (OMI-I###) tiers run.
    """
    raw = _read_bytes(input)
    source: dict[str, Any] = {"input": str(input)}
    if raw[:5] == b"%PDF-":
        result = _read(raw)
        if not result.present or result.payload is None:
            typer.echo(f"error: OM-IO-ABSENT: no om.json embedded in {input}", err=True)
            raise typer.Exit(3)
        payload = result.payload
        source |= {"kind": "pdf", "hashValid": result.hash_valid}
    else:
        payload = json.loads(raw.decode("utf-8"))  # reuse bytes; do not re-read stdin
        source["kind"] = "payload"

    schema_obj = _load_json(schema) if schema is not None else None
    report = _validate(payload, schema=schema_obj, as_of=as_of)
    _emit(
        {
            "source": source,
            "errors": [dataclasses.asdict(f) for f in report.errors],
            "warnings": [dataclasses.asdict(f) for f in report.warnings],
            "info": [dataclasses.asdict(f) for f in report.info],
            "ok": report.ok,
        }
    )
    _echo_human_errors(report.errors)
    failed = not report.ok or (strict and bool(report.warnings))
    raise typer.Exit(code=1 if failed else 0)


def _embed_pair(
    stem: str,
    pdf: Path,
    payload_path: Path,
    out_dir: Path,
    asserted_date: str,
    schema_obj: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate (if a schema is given) then embed one <name>.pdf + <name>.json pair.

    A pair with schema ERRORS is skipped and never embedded (schema errors block, §6); warnings do
    not block. Deterministic, zero inference. Returns a per-pair record for the summary.
    """
    data = _load_json(payload_path)
    if schema_obj is not None:
        report = _validate(data, schema=schema_obj)
        if report.errors:
            return {"name": stem, "action": "skipped", "reason": "schema-errors",
                    "codes": [e.code for e in report.errors]}
    src = pdf.read_bytes()
    warnings = [w.code for w in _reembed_warnings(src, data, asserted_date=asserted_date)]
    out_path = out_dir / f"{stem}.openom.pdf"
    out_path.write_bytes(_embed(src, data, asserted_date=asserted_date))
    return {"name": stem, "action": "embedded", "out": str(out_path), "warnings": warnings}


def _scan_once(
    in_dir: Path,
    out_dir: Path,
    asserted_date: str,
    schema_obj: dict[str, Any] | None,
    seen: dict[str, tuple[float, float]],
) -> list[dict[str, Any]]:
    """One pass: embed each <name>.pdf with a sibling <name>.json that changed since last seen."""
    events: list[dict[str, Any]] = []
    for pdf in sorted(in_dir.glob("*.pdf")):
        payload_path = pdf.with_suffix(".json")
        if not payload_path.is_file():
            continue  # not a complete pair yet
        sig = (pdf.stat().st_mtime, payload_path.stat().st_mtime)
        if seen.get(pdf.stem) == sig:
            continue  # unchanged since we last processed it
        record = _embed_pair(pdf.stem, pdf, payload_path, out_dir, asserted_date, schema_obj)
        seen[pdf.stem] = sig
        events.append(record)
    return events


@app.command()
@_guard
def watch(
    in_dir: Annotated[Path, typer.Argument(help="Folder watched for <name>.pdf+<name>.json pairs")],
    out: Annotated[Path, typer.Option(help="Output folder for <name>.openom.pdf")],
    asserted_date: Annotated[str, typer.Option(help="ISO 8601 assertion date stamped on embeds")],
    schema: Annotated[
        Path | None,
        typer.Option(help="JSON Schema; a payload with schema errors is skipped, not embedded"),
    ] = None,
    once: Annotated[
        bool,
        typer.Option(help="Process the current backlog once and exit (for cron/CI); no polling"),
    ] = False,
    interval: Annotated[
        float, typer.Option(help="Poll interval in seconds (ignored with --once)")
    ] = 2.0,
) -> None:
    """Watch a folder and auto-embed each <name>.pdf with a sibling <name>.json (server-side path).

    Deterministic, zero inference. A pair is (re)processed when its pdf/json changes; the produced
    <name>.openom.pdf lands in --out. With --schema, a payload with schema errors is logged and
    skipped (never embedded). --once drains the current backlog and exits; otherwise it polls every
    --interval seconds until interrupted (Ctrl-C).
    """
    out.mkdir(parents=True, exist_ok=True)
    schema_obj = _load_json(schema) if schema is not None else None
    seen: dict[str, tuple[float, float]] = {}

    if once:
        events = _scan_once(in_dir, out, asserted_date, schema_obj, seen)
        _emit({"watched": str(in_dir), "out": str(out), "events": events})
        return

    if not _output.quiet:
        typer.echo(f"watching {in_dir} -> {out} (every {interval}s; Ctrl-C to stop)", err=True)
    try:
        while True:
            for ev in _scan_once(in_dir, out, asserted_date, schema_obj, seen):
                typer.echo(json.dumps(ev, ensure_ascii=False), err=True)
            time.sleep(interval)
    except KeyboardInterrupt:  # pragma: no cover - interactive stop
        if not _output.quiet:
            typer.echo("stopped", err=True)


@app.command()
@_guard
def extract(
    pdf: Annotated[Path, typer.Argument(help="PDF to extract images from")],
    out_dir: Annotated[Path, typer.Option(help="Directory to write images into")],
    render_vector_pages: Annotated[
        bool, typer.Option(help="Also rasterize pages that have no raster images (vector-only)")
    ] = False,
) -> None:
    # Written filenames are img_<xref>.png / page_<n>.png (both integers), so no untrusted path
    # component can escape out_dir - path traversal is not reachable from payload/PDF content.
    data = _read_bytes(pdf)
    _emit(_extract_images(data, out_dir=out_dir, render_vector_pages=render_vector_pages))


@app.command(name="extract-text")
@_guard
def extract_text_cmd(
    pdf: Annotated[Path, typer.Argument(help="PDF to extract text + best-effort tables from")],
    page_range: Annotated[
        str | None,
        typer.Option("--pages", help="1-indexed pages: '3' | '1-5' | '2,4,7' (default all)"),
    ] = None,
    max_chars: Annotated[
        int, typer.Option(help="Max characters per page of output; paginate with --cursor")
    ] = 100_000,
    cursor: Annotated[
        str | None, typer.Option(help="Opaque cursor from a prior call's nextCursor, to continue")
    ] = None,
) -> None:
    """Extract paginated plain text + best-effort tables (the same deterministic pass the MCP
    om_extract_text tool uses). Zero inference; useful for feeding an OM's text to your own mapping
    step. Emits {text, tables, pageRange, truncated, nextCursor}."""
    result = _extract_text(
        _read_bytes(pdf), page_range=page_range, max_chars=max_chars, cursor=cursor
    )
    _emit(result)


@app.command()
def version() -> None:
    """Print the tool + spec versions."""
    _emit({"tool": "openom-cli", "toolVersion": _tool_version(), "specVersion": SPEC_VERSION})


@app.command()
@_guard
def conformance(
    spec_dir: Annotated[Path, typer.Option(help="Path to the spec/ directory")] = Path("spec"),
    role: Annotated[str | None, typer.Option(help="Filter vectors by role")] = None,
    level: Annotated[str | None, typer.Option(help="Filter vectors by level")] = None,
    impl_dir: Annotated[
        Path | None,
        typer.Option(
            help="Certify a THIRD-PARTY implementation: a dir with <name>.canonical (JCS bytes) "
            "and/or <name>.pdf (embedded output) per vector, compared to the goldens. Without "
            "it, the LOCAL implementation is checked."
        ),
    ] = None,
) -> None:
    """Run the conformance suite (§T [OM-REF-002]): reproduce the published vectors + sample
    outcomes. Without --impl-dir it checks the local implementation; with --impl-dir it certifies an
    external implementation's produced bytes/PDFs. Exit 0 if all checks pass, 1 otherwise."""
    checks: list[dict[str, Any]] = []
    vectors = spec_dir / "vectors"
    # [Mi8] The conformance vectors are NOT shipped in the wheel (they're the repo's /spec tree), so
    # a plain `pip install openom-cli && om conformance` can't find them. Fail with a clear hint
    # instead of a raw FileNotFoundError.
    if not (vectors / "manifest.json").is_file():
        typer.echo(
            f"error: conformance vectors not found under {spec_dir}/ "
            "(this command runs from a repo checkout; pass --spec-dir <path-to>/spec)",
            err=True,
        )
        raise typer.Exit(3)
    manifest = _load_json(vectors / "manifest.json")
    for vec in manifest["vectors"]:
        dims = vec.get("dimensions", {})
        if role is not None and role not in dims.get("role", []):
            continue
        if level is not None and level not in dims.get("level", []):
            continue
        payload = _load_json(vectors / vec["payload"])
        expected = _load_json(vectors / vec["expected"])
        if impl_dir is not None:
            # Certify the third party: hash THEIR canonical bytes; read THEIR PDF. A missing output
            # is a FAILED check, not a skip - else an empty --impl-dir would falsely pass.
            cbytes = impl_dir / f"{vec['name']}.canonical"
            checks.append(
                {
                    "check": f"vector:{vec['name']}:jcs",
                    "ok": cbytes.is_file()
                    and hash_bytes(cbytes.read_bytes()) == expected["jcs_sha256"],
                }
            )
            impl_pdf = impl_dir / f"{vec['name']}.pdf"
            if impl_pdf.is_file():
                res = _read(impl_pdf.read_bytes())
                checks.append(
                    {
                        "check": f"vector:{vec['name']}:pdf",
                        "ok": res.present and res.hash_valid is True,
                    }
                )
            continue
        got = hash_bytes(canonicalize(payload))
        checks.append({"check": f"vector:{vec['name']}:jcs", "ok": got == expected["jcs_sha256"]})
        pdf_path = vectors / vec["pdf"]
        if pdf_path.exists():
            res = _read(pdf_path.read_bytes())
            ok = res.present and res.hash_valid is True
            checks.append({"check": f"vector:{vec['name']}:pdf", "ok": ok})

    sample_manifest = spec_dir / "samples" / "manifest.json"
    if sample_manifest.exists():
        schema = _load_json(spec_dir / "om-0.1.schema.json")
        for s in _load_json(sample_manifest)["samples"]:
            payload = _load_json(spec_dir / "samples" / f"{s['name']}.json")
            report = _validate(payload, schema=schema)
            codes = {f.code for f in report.errors}
            if s["valid"]:
                ok = report.ok
            else:
                ok = not report.ok and all(c in codes for c in s["errorCodes"])
            checks.append({"check": f"sample:{s['name']}", "ok": ok})

    failures = [c["check"] for c in checks if not c["ok"]]
    _emit(
        {"total": len(checks), "passed": len(checks) - len(failures),
         "failed": len(failures), "failures": failures, "ok": not failures}
    )
    raise typer.Exit(code=0 if not failures else 1)


if __name__ == "__main__":
    app()
