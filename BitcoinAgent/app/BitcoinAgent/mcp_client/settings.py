"""Official Etherscan, Jupiter, and Phantom MCP endpoints and flags.

AgentCore Gateway MCP targets cannot attach an API key, so BitcoinAgent
connects to these servers from agent code when the env vars are set.
Never log or persist API keys.
"""

from __future__ import annotations

import os

ETHERSCAN_MCP_URL = "https://mcp.etherscan.io/mcp"
ETHERSCAN_DOCS_MCP_URL = "https://docs.etherscan.io/mcp"
JUPITER_DOCS_MCP_URL = "https://developers.jup.ag/docs/mcp"
PHANTOM_DOCS_MCP_URL = "https://docs.phantom.com/mcp"

_TRUTHY = {"1", "true", "yes", "on"}


def etherscan_api_key() -> str | None:
    key = os.getenv("ETHERSCAN_API_KEY", "").strip()
    return key or None


def etherscan_mcp_enabled() -> bool:
    return etherscan_api_key() is not None


def etherscan_docs_mcp_enabled() -> bool:
    if etherscan_mcp_enabled():
        return True
    return os.getenv("ETHERSCAN_DOCS_MCP", "").strip().lower() in _TRUTHY


def jupiter_api_key() -> str | None:
    key = os.getenv("JUPITER_API_KEY", "").strip()
    return key or None


def jupiter_docs_mcp_enabled() -> bool:
    if os.getenv("JUPITER_DOCS_MCP", "").strip().lower() in _TRUTHY:
        return True
    return jupiter_api_key() is not None


def phantom_app_id() -> str | None:
    """Portal App ID if set. Callers must not print or log the value."""
    app_id = os.getenv("PHANTOM_APP_ID", "").strip()
    return app_id or None


def phantom_app_id_set() -> bool:
    return phantom_app_id() is not None


def phantom_docs_mcp_enabled() -> bool:
    return os.getenv("PHANTOM_DOCS_MCP", "").strip().lower() in _TRUTHY
