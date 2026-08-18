# SPDX-License-Identifier: MIT
"""The ``om`` CLI over openom-core (spec §5a). Thin, deterministic, zero inference.

Commands: embed · read · inspect · validate · check · extract · conformance · version. JSON goes
to stdout (``--format pretty|compact``; ``--quiet`` suppresses it). A path of ``-`` means stdin
(input) or stdout (``embed --out -``) for pipe-friendly use. Exit codes: 0 ok · 1 validation/
conformance failure · 2 usage (typer) · 3 data/IO error (bad PDF/JSON, OM-IO-*). Warnings never
affect the exit code.
"""

from __future__ import annotations

import dataclasses
import functools
import json
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Annotated, Any, TypeVar, cast

import pikepdf
import typer
from openom_core.canonical import canonicalize, hash_bytes
from openom_core.embed import embed as _embed
from openom_core.embed import read as _read
from openom_core.embed import reembed_warnings as _reembed_warnings
from openom_core.errors import CanonicalizationError, PayloadTooLargeError
from openom_core.images import extract_images as _extract_images
from openom_core.inspect import inspect as _inspect
from openom_core.validate import validate as _validate

SPEC_VERSION = "0.1"


def _force_utf8(stream: object) -> None:
    """Emit UTF-8 on a text stream regardless of the OS console codepage (#18).

    On Windows with a legacy codepage (cp1252) — the default on Python < 3.15 or under
    ``PYTHONUTF8=0`` — the em-dashes / middots in help text and any non-ASCII in JSON output
    mojibake or raise UnicodeEncodeError. Reconfiguring to UTF-8 fixes it everywhere. Text layer
    only: the binary ``embed --out -`` path writes ``sys.stdout.buffer`` and is unaffected.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return  # e.g. a test harness replaced stdout with a plain object
    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError):  # detached / already-written stream — best-effort
        pass


for _std in (sys.stdout, sys.stderr):
    _force_utf8(_std)

app = typer.Typer(
    help="openOM deterministic engine — embed/read/inspect/validate/check/extract."
)

_F = TypeVar("_F", bound=Callable[..., Any])
_DATA_ERRORS = (
    CanonicalizationError,
    PayloadTooLargeError,
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


@app.callback()
def _main(
    output_format: Annotated[
        str, typer.Option("--format", help="stdout JSON format: pretty | compact")
    ] = "pretty",
    quiet: Annotated[
        bool, typer.Option("--quiet", help="Suppress stdout (exit code + stderr only)")
    ] = False,
) -> None:
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


def _load_json(path: Path) -> dict[str, Any]:
    text = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    return cast("dict[str, Any]", json.loads(text))


def _emit(obj: Any) -> None:
    if _output.quiet:
        return
    if _output.fmt == "compact":
        typer.echo(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
    else:
        typer.echo(json.dumps(obj, indent=2, ensure_ascii=False))


@app.command()
@_guard
def embed(
    pdf: Annotated[Path, typer.Argument(help="Input PDF")],
    payload: Annotated[Path, typer.Option(help="Payload JSON to embed")],
    out: Annotated[Path, typer.Option(help="Output PDF path")],
    asserted_date: Annotated[str, typer.Option(help="ISO 8601 assertion date")],
) -> None:
    src = _read_bytes(pdf)
    data = _load_json(payload)
    for w in _reembed_warnings(src, data, asserted_date=asserted_date):
        typer.echo(f"warning {w.code} {w.path}: {w.message}", err=True)
    _write_bytes(out, _embed(src, data, asserted_date=asserted_date))
    # Status to stderr so `--out -` keeps a clean binary PDF on stdout for piping.
    if not _output.quiet:
        typer.echo(f"embedded om.json -> {'<stdout>' if str(out) == '-' else out}", err=True)


@app.command()
@_guard
def read(pdf: Annotated[Path, typer.Argument(help="PDF to read")]) -> None:
    result = _read(_read_bytes(pdf))
    _emit(
        {
            "present": result.present,
            "payload": result.payload,
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
    failed = not report.ok or (strict and bool(report.warnings))
    raise typer.Exit(code=1 if failed else 0)


@app.command()
@_guard
def extract(
    pdf: Annotated[Path, typer.Argument(help="PDF to extract images from")],
    out_dir: Annotated[Path, typer.Option(help="Directory to write images into")],
) -> None:
    # Written filenames are img_<xref>.png (xref is an integer), so no untrusted path component
    # can escape out_dir — path traversal is not reachable from payload/PDF content.
    _emit(_extract_images(_read_bytes(pdf), out_dir=out_dir))


@app.command()
def version() -> None:
    """Print the tool + spec versions."""
    try:
        tool_version = _pkg_version("openom-cli")
    except PackageNotFoundError:  # pragma: no cover — running from a source tree
        tool_version = "0.0.0-dev"
    _emit({"tool": "openom-cli", "toolVersion": tool_version, "specVersion": SPEC_VERSION})


@app.command()
@_guard
def conformance(
    spec_dir: Annotated[Path, typer.Option(help="Path to the spec/ directory")] = Path("spec"),
    role: Annotated[str | None, typer.Option(help="Filter vectors by role")] = None,
    level: Annotated[str | None, typer.Option(help="Filter vectors by level")] = None,
) -> None:
    """Run the conformance suite (§T [OM-REF-002]): reproduce the published vectors + sample
    outcomes with the local implementation. Exit 0 if all checks pass, 1 otherwise."""
    checks: list[dict[str, Any]] = []
    vectors = spec_dir / "vectors"
    manifest = _load_json(vectors / "manifest.json")
    for vec in manifest["vectors"]:
        dims = vec.get("dimensions", {})
        if role is not None and role not in dims.get("role", []):
            continue
        if level is not None and level not in dims.get("level", []):
            continue
        payload = _load_json(vectors / vec["payload"])
        expected = _load_json(vectors / vec["expected"])
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
