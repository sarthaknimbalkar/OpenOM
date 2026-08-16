#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Local corpus characterization / classifier-tuning tool (Task 8).

Runs ``inspect`` over every PDF under ``OMs/`` (the confidential, git-ignored corpus) and
prints class, confidence, textCoverage, and page count. Given a labels file
(JSON ``{relpath: "native"|"hybrid"|"scanned"}``) it also prints a confusion matrix so
thresholds can be tuned against real ground truth.

    python core/scripts/characterize_corpus.py [--labels labels.json]

Not a CI test: the corpus is not committed, and ground-truth labels require human judgment (Q3).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from openom_core.inspect import inspect

ROOT = Path(__file__).resolve().parents[2]
OMS = ROOT / "OMs"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=None, help="JSON {relpath: class}")
    args = parser.parse_args()

    if not OMS.exists():
        print(f"corpus not present: {OMS}")
        return

    labels: dict[str, str] = (
        json.loads(args.labels.read_text(encoding="utf-8")) if args.labels else {}
    )
    dist: Counter[str] = Counter()
    confusion: Counter[tuple[str, str]] = Counter()
    pdfs = sorted(OMS.rglob("*.pdf"))

    for pdf in pdfs:
        rel = pdf.relative_to(OMS).as_posix()
        try:
            prof = inspect(pdf.read_bytes())
        except Exception as exc:  # noqa: BLE001 — tool: report and keep going
            print(f"ERROR {rel}: {exc}")
            continue
        cls = prof["class"]
        dist[cls] += 1
        print(
            f"{cls:8} conf={prof['classConfidence']:.2f} tc={prof['textCoverage']:.2f} "
            f"pages={prof['pages']:>3}  {rel}"
        )
        if rel in labels:
            confusion[(labels[rel], cls)] += 1

    print(f"\nDISTRIBUTION over {len(pdfs)} files: {dict(dist)}")
    if confusion:
        correct = sum(n for (t, p), n in confusion.items() if t == p)
        total = sum(confusion.values())
        print(f"ACCURACY: {correct}/{total}")
        print("CONFUSION (true -> predicted):")
        for (t, p), n in sorted(confusion.items()):
            print(f"  {t:8} -> {p:8}: {n}{'' if t == p else '   <-- MISS'}")


if __name__ == "__main__":
    main()
