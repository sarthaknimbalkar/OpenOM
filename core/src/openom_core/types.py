# SPDX-License-Identifier: MIT
"""Typed view of the openOM 0.1 payload for Python authors ([Ma3], parity with /js OMPayload).

These are a developer convenience for constructing/reading payloads with editor help — the
deterministic core verbs accept ``Mapping[str, Any]`` (a payload may be a not-yet-validated draft;
validation is the separate gate). The shapes are drift-locked to spec/om-0.1.schema.json by
tests/test_types.py: each TypedDict's keys MUST equal the schema's properties at that path.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class AssertedBy(TypedDict):
    broker: str
    brokerage: str
    license: str
    website: NotRequired[str]
    licenseJurisdiction: NotRequired[str]
    licenseAuthority: NotRequired[str]


class Deal(TypedDict, total=False):
    askingPrice: float
    capRate: float
    noi: float
    noiType: str  # "in-place" | "pro-forma"
    noiAsOfDate: str
    pricePerSF: float
    pricePerUnit: float
    status: str


class Property(TypedDict, total=False):
    propertyType: str
    address: dict[str, Any]
    geo: dict[str, Any]
    apn: str
    buildingSF: float
    lotAcres: float
    yearBuilt: int
    yearRenovated: int
    units: int
    occupancy: float


class Meta(TypedDict):
    supersedes: str | None
    sourceDocHash: NotRequired[str]
    signature: NotRequired[dict[str, Any] | None]
    imageRights: NotRequired[str]
    canonicalUrl: NotRequired[str]


# @context / @type require the functional TypedDict form (not valid Python identifiers).
OMPayload = TypedDict(
    "OMPayload",
    {
        "@context": list[str],
        "@type": str,
        "specVersion": str,
        "currency": NotRequired[str],
        "assertedBy": AssertedBy,
        "assertedDate": str,
        "property": NotRequired[Property],
        "deal": NotRequired[Deal],
        "lease": NotRequired[dict[str, Any]],
        "meta": Meta,
        "ext": NotRequired[dict[str, Any]],
    },
)
"""The openOM 0.1 payload (alias: RealEstateListing). See module docstring for the trust caveat."""

RealEstateListing = OMPayload
