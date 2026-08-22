"""[Ma7] om-mcp-http must be configurable and safe by default (no world-open, rebinding-off)."""

from __future__ import annotations

import pytest

from openom_mcp.server import http_config_from_env


def test_default_binds_loopback_no_rebinding_needed(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in list(__import__("os").environ):
        if k.startswith("OPENOM_MCP_"):
            monkeypatch.delenv(k, raising=False)
    host, port, kwargs = http_config_from_env()
    assert host == "127.0.0.1"  # NOT 0.0.0.0
    assert port == 8080
    assert kwargs["dns_rebinding_protection"] is False  # loopback: not needed


def test_public_bind_defaults_dns_rebinding_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENOM_MCP_HOST", "0.0.0.0")
    host, _port, kwargs = http_config_from_env()
    assert host == "0.0.0.0"
    assert kwargs["dns_rebinding_protection"] is True  # auto-on when world-bound


def test_env_overrides_are_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENOM_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("OPENOM_MCP_PORT", "9000")
    monkeypatch.setenv("OPENOM_MCP_RATE_LIMIT", "10")
    monkeypatch.setenv("OPENOM_MCP_RATE_WINDOW", "5")
    monkeypatch.setenv("OPENOM_MCP_MAX_FETCH_BYTES", "1024")
    monkeypatch.setenv("OPENOM_MCP_DNS_REBINDING", "false")
    monkeypatch.setenv("OPENOM_MCP_ALLOWED_HOSTS", "mcp.example.com, api.example.com")
    monkeypatch.setenv("OPENOM_MCP_ALLOWED_ORIGINS", "https://app.example.com")
    _host, port, kwargs = http_config_from_env()
    assert port == 9000
    assert kwargs["rate_limit"] == 10
    assert kwargs["rate_window_seconds"] == 5
    assert kwargs["max_fetch_bytes"] == 1024
    assert kwargs["dns_rebinding_protection"] is False  # explicit override wins over auto
    assert kwargs["allowed_hosts"] == ["mcp.example.com", "api.example.com"]
    assert kwargs["allowed_origins"] == ["https://app.example.com"]


def test_bad_int_env_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENOM_MCP_PORT", "notanint")
    with pytest.raises(SystemExit):
        http_config_from_env()
