"""M3 Task 7: the cardinal-rule boundary at the module level. The open /mcp server registers no
inference tool, imports no model client, and only exposes the paid-extraction seam as a 402. This
complements the dependency-level `boundary` CI job (pip-freeze) with an import-graph assertion.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys

from openom_mcp import server
from openom_mcp.extraction import InferenceExtractor, payment_required
from openom_mcp.tools import ToolError

# Known inference SDKs that MUST NOT be importable by the open server (§6a).
INFERENCE_LIBS = {
    "openai", "anthropic", "cohere", "langchain", "llama_index", "transformers",
    "torch", "tensorflow", "onnxruntime", "sentence_transformers", "litellm", "vllm",
}

DETERMINISTIC_TOOLS = [
    "om_embed", "om_extract_images", "om_extract_text", "om_inspect",
    "om_read", "om_request_upload", "om_validate",
]


def test_payment_required_is_a_402_seam() -> None:
    err = payment_required()
    assert isinstance(err, ToolError) and err.code == "OM-IO-402"


def test_inference_extractor_is_protocol_only() -> None:
    # It is a structural Protocol with no concrete binding anywhere in the open server.
    assert getattr(InferenceExtractor, "_is_runtime_protocol", False) is True


def test_only_deterministic_tools_registered() -> None:
    names = sorted(t.name for t in asyncio.run(server.mcp.list_tools()))
    assert names == DETERMINISTIC_TOOLS  # no inference/extract-payload tool


def test_mcp_imports_no_model_client() -> None:
    # Import the whole /mcp graph in an ISOLATED subprocess (-I) so sys.modules starts clean. This
    # measures exactly what importing /mcp pulls in - immune to an inference SDK that another test
    # (or a dev's shared env) already loaded into this process. An inference lib that isn't
    # installed can never be imported by /mcp, so its absence is a pass; a leak fails.
    code = (
        "import importlib, pkgutil, sys, json; import openom_mcp\n"
        "for m in pkgutil.iter_modules(openom_mcp.__path__, 'openom_mcp.'):\n"
        "    importlib.import_module(m.name)\n"
        f"libs = {sorted(INFERENCE_LIBS)!r}\n"
        "print(json.dumps(sorted(set(libs) & set(sys.modules))))\n"
    )
    out = subprocess.run(  # noqa: S603 - fixed argv, our own interpreter
        [sys.executable, "-I", "-c", code], capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    leaked = json.loads(out.stdout.strip().splitlines()[-1])
    assert not leaked, f"an inference client was imported by /mcp: {leaked}"
