import logging
import os

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

from mcp_client.settings import (
    ETHERSCAN_DOCS_MCP_URL,
    ETHERSCAN_MCP_URL,
    etherscan_api_key,
    etherscan_docs_mcp_enabled,
    etherscan_mcp_enabled,
)

logger = logging.getLogger(__name__)

# Injected by AgentCore after deploy. Unavailable during `agentcore dev`.
GATEWAY_URL = os.getenv("AGENTCORE_GATEWAY_BITCOINGATEWAY_URL")


def get_gateway_mcp_client() -> MCPClient | None:
    """Return a Strands MCP client for BitcoinGateway, or None in local dev."""
    if not GATEWAY_URL:
        logger.info("Gateway URL unset; running without BitcoinGateway tools.")
        return None
    return MCPClient(lambda: streamablehttp_client(GATEWAY_URL))


def get_etherscan_mcp_client() -> MCPClient | None:
    """Return a client for the official Etherscan data MCP, or None if unset.

    Etherscan authenticates with ``Authorization: Bearer <api key>``.
    AgentCore Gateway cannot inject that header on MCP targets, so this
    client talks to ``mcp.etherscan.io`` directly.
    """
    if not etherscan_mcp_enabled():
        logger.info("ETHERSCAN_API_KEY unset; running without Etherscan MCP tools.")
        return None
    key = etherscan_api_key()
    headers = {"Authorization": f"Bearer {key}"}
    return MCPClient(lambda: streamablehttp_client(ETHERSCAN_MCP_URL, headers=headers))


def get_etherscan_docs_mcp_client() -> MCPClient | None:
    """Return a client for the public Etherscan docs MCP, or None if disabled."""
    if not etherscan_docs_mcp_enabled():
        return None
    return MCPClient(lambda: streamablehttp_client(ETHERSCAN_DOCS_MCP_URL))
