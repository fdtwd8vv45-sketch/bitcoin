from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_client.settings import (
    ETHERSCAN_DOCS_MCP_URL,
    ETHERSCAN_MCP_URL,
    etherscan_api_key,
    etherscan_docs_mcp_enabled,
    etherscan_mcp_enabled,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CURSOR_MCP_JSON = REPO_ROOT / ".cursor" / "mcp.json"


class CursorMcpConfigTests(unittest.TestCase):
    def test_project_mcp_json_points_at_official_etherscan_servers(self) -> None:
        config = json.loads(CURSOR_MCP_JSON.read_text(encoding="utf-8"))
        servers = config["mcpServers"]
        self.assertEqual(servers["etherscan"]["url"], ETHERSCAN_MCP_URL)
        self.assertEqual(
            servers["etherscan"]["headers"]["Authorization"],
            "Bearer ${env:ETHERSCAN_API_KEY}",
        )
        self.assertEqual(servers["etherscan-docs"]["url"], ETHERSCAN_DOCS_MCP_URL)
        dumped = json.dumps(config)
        self.assertNotIn("YOUR_ETHERSCAN_API_KEY", dumped)
        self.assertNotRegex(dumped, r"Bearer [A-Za-z0-9]{8,}")


class EtherscanMcpSettingsTests(unittest.TestCase):
    def test_disabled_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ETHERSCAN_API_KEY", None)
            os.environ.pop("ETHERSCAN_DOCS_MCP", None)
            self.assertIsNone(etherscan_api_key())
            self.assertFalse(etherscan_mcp_enabled())
            self.assertFalse(etherscan_docs_mcp_enabled())

    def test_key_enables_data_and_docs(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": " test-key "}, clear=False):
            os.environ.pop("ETHERSCAN_DOCS_MCP", None)
            self.assertEqual(etherscan_api_key(), "test-key")
            self.assertTrue(etherscan_mcp_enabled())
            self.assertTrue(etherscan_docs_mcp_enabled())

    def test_docs_only_flag(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_DOCS_MCP": "1"}, clear=False):
            os.environ.pop("ETHERSCAN_API_KEY", None)
            self.assertFalse(etherscan_mcp_enabled())
            self.assertTrue(etherscan_docs_mcp_enabled())


if __name__ == "__main__":
    unittest.main()
