# SPDX-License-Identifier: MIT
"""A per-user broker profile so identity (name/brokerage/license) is set once, never retyped.

Brokers asked for a settable profile on the CLI; this is it. Stored device-locally at
``<app-dir>/profile.json`` (``%APPDATA%\\openom`` on Windows, ``~/.config/openom`` on Linux).
``om init`` and ``om embed`` fill a payload's ``assertedBy`` from it - payload values always win,
the profile only fills blanks, and a missing/corrupt file never breaks a command (it reads as {}).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

APP_NAME = "openom"
_FIELDS = ("broker", "brokerage", "license")


def config_dir() -> Path:
    return Path(typer.get_app_dir(APP_NAME))


def profile_path() -> Path:
    return config_dir() / "profile.json"


def load_profile() -> dict[str, Any]:
    """The saved profile, or {} if absent/unreadable. Never raises (embed must not break on it)."""
    try:
        data = json.loads(profile_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_profile(
    *, broker: str | None, brokerage: str | None, license: str | None
) -> dict[str, Any]:
    """Overlay the given (non-None) fields onto the stored profile's ``assertedBy`` and persist."""
    prof = load_profile()
    asserted = dict(prof.get("assertedBy") or {})
    for key, value in {"broker": broker, "brokerage": brokerage, "license": license}.items():
        if value is not None:
            asserted[key] = value
    prof["assertedBy"] = asserted
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
    return prof


def profile_asserted_by() -> dict[str, str]:
    """The saved ``assertedBy`` mapping (broker/brokerage/license), or {}."""
    asserted = load_profile().get("assertedBy")
    return asserted if isinstance(asserted, dict) else {}


def merge_into(payload: dict[str, Any]) -> bool:
    """Fill missing/blank ``assertedBy`` broker/brokerage/license from the saved profile.

    Payload values always win; the profile only fills gaps. Returns True if anything was filled,
    so the caller can tell the user it happened.
    """
    saved = profile_asserted_by()
    if not saved:
        return False
    asserted = payload.get("assertedBy")
    asserted = dict(asserted) if isinstance(asserted, dict) else {}
    filled = False
    for key in _FIELDS:
        if saved.get(key) and not asserted.get(key):
            asserted[key] = saved[key]
            filled = True
    if filled:
        payload["assertedBy"] = asserted
    return filled
