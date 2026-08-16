"""The ``om`` CLI over openom-core (spec §5a). Thin, deterministic, zero inference.

Commands: embed · read · inspect · validate · extract. JSON is printed compactly to stdout;
``om validate`` exits non-zero on schema errors (warnings never block).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from openom_core.embed import embed as _embed
from openom_core.embed import read as _read
from openom_core.images import extract_images as _extract_images
from openom_core.inspect import inspect as _inspect
from openom_core.validate import validate as _validate

app = typer.Typer(help="OpenOM deterministic engine — embed/read/inspect/validate/extract.")


def _load_json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def _emit(obj: Any) -> None:
    typer.echo(json.dumps(obj, indent=2, ensure_ascii=False))


@app.command()
def embed(
    pdf: Annotated[Path, typer.Argument(help="Input PDF")],
    payload: Annotated[Path, typer.Option(help="Payload JSON to embed")],
    out: Annotated[Path, typer.Option(help="Output PDF path")],
    asserted_date: Annotated[str, typer.Option(help="ISO 8601 assertion date")],
) -> None:
    out.write_bytes(_embed(pdf.read_bytes(), _load_json(payload), asserted_date=asserted_date))
    typer.echo(f"embedded om.json -> {out}")


@app.command()
def read(pdf: Annotated[Path, typer.Argument(help="PDF to read")]) -> None:
    result = _read(pdf.read_bytes())
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
def inspect(pdf: Annotated[Path, typer.Argument(help="PDF to inspect")]) -> None:
    _emit(_inspect(pdf.read_bytes()))


@app.command()
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
            "ok": report.ok,
        }
    )
    raise typer.Exit(code=0 if report.ok else 1)


@app.command()
def extract(
    pdf: Annotated[Path, typer.Argument(help="PDF to extract images from")],
    out_dir: Annotated[Path, typer.Option(help="Directory to write images into")],
) -> None:
    _emit(_extract_images(pdf.read_bytes(), out_dir=out_dir))


if __name__ == "__main__":
    app()
