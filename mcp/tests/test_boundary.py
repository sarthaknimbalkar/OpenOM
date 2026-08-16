"""M3 Task 7: the cardinal-rule boundary at the module level. The open /mcp server registers no
inference tool, imports no model client, and only exposes the paid-extraction seam as a 402. This
complements the dependency-level `boundary` CI job (pip-freeze) with an import-graph assertion.
"""

from __future__ import annotations

import asyncio
import importlib
import pkgutil
import sys

import openom_mcp
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
    for module in pkgutil.iter_modules(openom_mcp.__path__, "openom_mcp."):
        importlib.import_module(module.name)
    leaked = INFERENCE_LIBS & set(sys.modules)
    assert not leaked, f"an inference client was imported by /mcp: {sorted(leaked)}"
