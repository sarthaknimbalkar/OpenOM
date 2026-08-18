#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Generate the cross-language JCS differential-fuzz corpus (#129).

The RFC 8785 canonicalization is the anti-fork keystone: if the Python and TS reference impls ever
serialize the same value to different bytes, a PDF verifies in one client and fails in another.
This produces a DETERMINISTIC, edge-weighted corpus of accepted payloads + their canonical hashes.
Both cores canonicalize the SAME corpus and MUST match `expected` byte-for-byte (test_fuzz.py /
fuzz.test.ts). The generator is seeded (no Date/urandom) so re-running is a no-op - a diff means a
hash moved. Run after any canonicalization change:  python core/scripts/gen_fuzz_corpus.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from openom_core.canonical import CanonicalizationError, canonicalize, hash_bytes

OUT = Path(__file__).resolve().parents[2] / "spec" / "vectors" / "fuzz"
SEED = 20260818  # fixed seed -> reproducible corpus (no Date/urandom)
COUNT = 600

# Values that historically fork JCS number/string serialization - the fuzz weights toward these.
_NUM_EDGES = [
    0, -0.0, 1, -1, 2**53 - 1, -(2**53 - 1), 0.1, -0.1, 0.5, 1.5,
    1e-7, 1.0000001, 9.999999e-7, 0.0000001, 123456.789, 1e-6, 1e-8,
    3.141592653589793, 2.718281828459045, 100.0, 0.0001, 1234567890, 42,
]
# Non-ASCII given as escapes so the source file stays pure ASCII (avoids encoding surprises).
_STR_EDGES = [
    "", "a", "A", "z", "é", "café",  # e-acute (NFC precomposed)
    "\U0001f600", "\U0001f4a9 tail",  # astral / surrogate-pair strings
    "line1\nline2", "tab\there", 'quote"q', "back\\slash", "slash/fwd",
    "中文", "key sort z", "key sort a",
]
_KEY_EDGES = ["a", "b", "A", "z", "é", "\U0001f600key", "10", "2", "中", "Z", "aa"]


def _rand_value(rng: random.Random, depth: int) -> object:
    if depth >= 4:
        kind = rng.choice(["num", "str", "bool", "null"])
    else:
        kind = rng.choices(
            ["num", "str", "bool", "null", "arr", "obj"], weights=[30, 30, 8, 8, 12, 12]
        )[0]
    if kind == "num":
        v = rng.choice(_NUM_EDGES)
        return v if rng.random() < 0.7 else rng.uniform(-1e6, 1e6)
    if kind == "str":
        if rng.random() < 0.8:
            return rng.choice(_STR_EDGES)
        return "".join(rng.choice("abcXYZ é中") for _ in range(rng.randint(0, 8)))
    if kind == "bool":
        return rng.random() < 0.5
    if kind == "null":
        return None
    if kind == "arr":
        return [_rand_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    keys = rng.sample(_KEY_EDGES, k=rng.randint(1, min(5, len(_KEY_EDGES))))
    return {k: _rand_value(rng, depth + 1) for k in keys}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    corpus: list[dict] = []
    while len(corpus) < COUNT:
        keys = rng.sample(_KEY_EDGES, k=rng.randint(1, 5))
        obj = {k: _rand_value(rng, 1) for k in keys}
        try:
            canonicalize(obj)  # keep only inputs BOTH impls accept (skip range/NFC-dup rejections)
        except CanonicalizationError:
            continue
        corpus.append(obj)

    dumped = (json.dumps(o, ensure_ascii=False, sort_keys=False) for o in corpus)
    corpus_txt = "\n".join(dumped) + "\n"
    expected_txt = "\n".join(hash_bytes(canonicalize(o)) for o in corpus) + "\n"
    (OUT / "corpus.jsonl").write_text(corpus_txt, encoding="utf-8", newline="\n")
    (OUT / "expected.jsonl").write_text(expected_txt, encoding="utf-8", newline="\n")
    print(f"wrote {len(corpus)} fuzz vectors + expected hashes -> {OUT}")


if __name__ == "__main__":
    main()
