#!/usr/bin/env python
"""Generate /spec/vectors/expected/*.json + manifest.json from the payloads (spec §B).

Each expected file records the integrity hash and the base64 of the *exact* JCS bytes, so any
implementation (Python or the Track B TypeScript reader) can compare byte-for-byte and by hash
without ambiguity. Run after any payload change:  python core/scripts/gen_vectors.py
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from openom_core.canonical import canonicalize, hash_bytes

ROOT = Path(__file__).resolve().parents[2]
VECTORS = ROOT / "spec" / "vectors"
PAYLOADS = VECTORS / "payloads"
EXPECTED = VECTORS / "expected"

# (role, level) tags per vector (§B [OM-VEC-006]); pathology tags added as those vectors land.
DIMENSIONS: dict[str, dict[str, list[str]]] = {
    "cafe": {"role": ["producer", "consumer"], "level": ["L1"], "pathology": []},
    "unicode": {"role": ["producer", "consumer"], "level": ["L1"], "pathology": []},
    "numbers": {"role": ["producer", "consumer"], "level": ["L1"], "pathology": []},
    "sample-stnl": {"role": ["producer", "consumer", "validator"], "level": ["L1"], "pathology": []},
}


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    EXPECTED.mkdir(parents=True, exist_ok=True)
    vectors = []
    for payload_path in sorted(PAYLOADS.glob("*.json")):
        name = payload_path.stem
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        jcs = canonicalize(payload)
        _write_json(
            EXPECTED / f"{name}.json",
            {
                "payload": f"payloads/{name}.json",
                "jcs_sha256": hash_bytes(jcs),
                "jcs_b64": base64.b64encode(jcs).decode("ascii"),
            },
        )
        vectors.append(
            {
                "name": name,
                "payload": f"payloads/{name}.json",
                "expected": f"expected/{name}.json",
                "dimensions": DIMENSIONS.get(
                    name, {"role": ["producer", "consumer"], "level": ["L1"], "pathology": []}
                ),
            }
        )
    _write_json(
        VECTORS / "manifest.json",
        {"specVersion": "0.1", "suite": "openom-vectors", "vectors": vectors},
    )
    print(f"wrote {len(vectors)} vectors + manifest.json")


if __name__ == "__main__":
    main()
