"""Official Etherscan MCP endpoints and enablement flags.

AgentCore Gateway MCP targets cannot attach an API key, so BitcoinAgent
connects to these servers from agent code when the env vars are set.
Never log or persist the API key.
"""

from __future__ import annotations

import os

ETHERSCAN_MCP_URL = "https://mcp.etherscan.io/mcp"
ETHERSCAN_DOCS_MCP_URL = "https://docs.etherscan.io/mcp"

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
