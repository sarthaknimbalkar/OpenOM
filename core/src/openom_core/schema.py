# SPDX-License-Identifier: MIT
"""Canonical loader for the openOM 0.1 JSON Schema (#148/#149).

Resolves the schema in a way that works BOTH in a pip-installed wheel and an editable/dev checkout,
and caches the parsed dict so hosted callers do not re-read + re-parse it per request:

  * wheel     - the schema is shipped as package data (force-included from /spec at build; see
                core/pyproject.toml) and read via importlib.resources.
  * editable  - package data isn't materialized, so fall back to the repo's /spec single source.

Returning the SAME cached object also lets the validator cache in validate.py key on its identity.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

SCHEMA_NAME = "om-0.1.schema.json"


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    """The openOM 0.1 payload JSON Schema, parsed and cached."""
    try:
        packaged = resources.files("openom_core").joinpath(SCHEMA_NAME)
        if packaged.is_file():
            return json.loads(packaged.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        pass
    repo = Path(__file__).resolve().parents[3] / "spec" / SCHEMA_NAME
    return json.loads(repo.read_text(encoding="utf-8"))
