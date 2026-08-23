# SPDX-License-Identifier: MIT
"""openOM deterministic core.

Embed / read / inspect / validate machine-readable, broker-asserted payloads in
commercial-real-estate offering-memorandum PDFs. Zero inference, ever (CLAUDE.md Rule 1).

The stable public surface is re-exported here, so an integrator writes
``from openom_core import embed, read, validate, load_schema`` (submodule paths keep working too).
See the spec Part II §A-§E, §H-§J.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from .canonical import canonicalize, hash_bytes, payload_hash
from .embed import ReadResult, embed, read, reembed_warnings
from .errors import CanonicalizationError, Finding, PayloadTooLargeError, Severity
from .images import ImageManifest, extract_images
from .inspect import Profile, classify
from .schema import load_schema
from .summary import DealSummary, summarize_deal
from .text import TextResult, extract_text
from .types import OMPayload, RealEstateListing
from .validate import Report, Tolerances, validate

try:  # single source of truth: the installed package metadata (matches `pip show` / the wheel)
    __version__ = _pkg_version("openom-core")
except PackageNotFoundError:  # editable/source tree without an installed dist
    __version__ = "0.0.0+unknown"

#: The openOM spec version this library targets. Drift-locked to the schema by tests/test_types.py.
SPEC_VERSION = "0.1"

__all__ = [
    "SPEC_VERSION",
    "__version__",
    # verbs
    "embed",
    "read",
    "reembed_warnings",
    "validate",
    "classify",
    "extract_text",
    "extract_images",
    "canonicalize",
    "hash_bytes",
    "payload_hash",
    "load_schema",
    "summarize_deal",
    # result / option types
    "ReadResult",
    "Report",
    "Tolerances",
    "Profile",
    "TextResult",
    "ImageManifest",
    "DealSummary",
    "Finding",
    "Severity",
    "OMPayload",
    "RealEstateListing",
    # errors
    "CanonicalizationError",
    "PayloadTooLargeError",
]
