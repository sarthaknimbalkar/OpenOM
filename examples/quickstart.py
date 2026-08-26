#!/usr/bin/env python3
"""openOM 60-second quickstart: embed -> read -> validate, end to end, no edits needed.

    pip install openom-core        # published on PyPI
    python quickstart.py           # runs anywhere - self-contained, no repo clone needed

Uses a blank stand-in PDF + an inline sample payload so it runs from a pip-only install (nothing is
read from the repo tree). Swap in your own OM PDF and payload to embed for real. Deterministic; zero
inference.
"""

import io

import pikepdf

# The stable public surface is re-exported from the package root (no deep submodule imports needed).
from openom_core import embed, read, validate

# An inline, schema-valid sample payload, so this script is self-contained (no spec/ files required).
payload = {
    "@context": ["https://schema.org", "https://openom.app/ns/0.1"],
    "@type": "RealEstateListing",
    "specVersion": "0.1",
    "assertedBy": {"broker": "Jane Example", "brokerage": "Example Advisors", "license": "TX 12345"},
    "assertedDate": "2026-08-15",
    "property": {
        "address": {
            "streetAddress": "123 Main St",
            "addressLocality": "Austin",
            "addressRegion": "TX",
            "postalCode": "78701",
            "addressCountry": "US",
        },
        "buildingSF": 9100,
    },
    "deal": {
        "askingPrice": 1850000,
        "capRate": 0.0625,  # a decimal fraction: 6.25% is 0.0625, NOT 6.25
        "noi": 115625,
        "noiType": "in-place",
        "noiAsOfDate": "2026-06-30",
        "status": "active",
    },
    "meta": {"supersedes": None},
}

# A blank stand-in for your offering memorandum (embedding never changes the page content).
doc = pikepdf.new()
doc.add_blank_page(page_size=(612, 792))
buf = io.BytesIO()
doc.save(buf)

embedded = embed(buf.getvalue(), payload, asserted_date=str(payload["assertedDate"]))
r = read(embedded)
print(f"read     -> present={r.present}  hashValid={r.hash_valid}")

report = validate(r.payload)  # defaults to the bundled 0.1 schema (openom_core.load_schema)
errs = len(report.errors)
warns = len(report.warnings)
print(f"validate -> ok={report.ok}  errors={errs}  warnings={warns}")
print(f"deal     -> price={r.payload['deal']['askingPrice']}  capRate={r.payload['deal']['capRate']}")
print("\nThe PDF now carries a hash-verified, broker-asserted payload - byte-identical to the eye.")
