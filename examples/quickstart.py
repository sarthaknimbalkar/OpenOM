#!/usr/bin/env python3
"""openOM 60-second quickstart: embed -> read -> validate, end to end, no edits needed.

    pip install openom-core
    python examples/quickstart.py     # run from the repo root

Uses a blank stand-in PDF + a committed sample payload so it runs anywhere. Swap in your own OM
PDF and payload to embed for real. Deterministic; zero inference.
"""
import io
import json
from pathlib import Path

import pikepdf
from openom_core.embed import embed, read
from openom_core.validate import validate

spec = Path(__file__).resolve().parents[1] / "spec"
payload = json.loads((spec / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))
schema = json.loads((spec / "om-0.1.schema.json").read_text(encoding="utf-8"))

# A blank stand-in for your offering memorandum (embedding never changes the page content).
doc = pikepdf.new()
doc.add_blank_page(page_size=(612, 792))
buf = io.BytesIO()
doc.save(buf)

embedded = embed(buf.getvalue(), payload, asserted_date=str(payload["assertedDate"]))
r = read(embedded)
print(f"read     -> present={r.present}  hashValid={r.hash_valid}")

report = validate(r.payload, schema=schema)
errs = len(report.errors)
warns = len(report.warnings)
print(f"validate -> ok={report.ok}  errors={errs}  warnings={warns}")
print(f"deal     -> price={r.payload['deal']['askingPrice']}  capRate={r.payload['deal']['capRate']}")
print("\nThe PDF now carries a hash-verified, broker-asserted payload - byte-identical to the eye.")
