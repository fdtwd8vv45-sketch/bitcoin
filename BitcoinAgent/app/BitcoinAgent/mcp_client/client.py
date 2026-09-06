import logging
import os

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# Injected by AgentCore after deploy. Unavailable during `agentcore dev`.
GATEWAY_URL = os.getenv("AGENTCORE_GATEWAY_BITCOINGATEWAY_URL")


def get_gateway_mcp_client() -> MCPClient | None:
    """Return a Strands MCP client for BitcoinGateway, or None in local dev."""
    if not GATEWAY_URL:
        logger.info("Gateway URL unset; running without BitcoinGateway tools.")
        return None
    return MCPClient(lambda: streamablehttp_client(GATEWAY_URL))
