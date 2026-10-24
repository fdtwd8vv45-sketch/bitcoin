from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bitcoin_tools import developer_howto
from cubic import (
    CLI_INSTALL_CURL,
    CLI_INSTALL_NPX,
    CLI_PACKAGE,
    MCP_DOCS_URL,
    MCP_URL,
    WRITE_TOOLS,
    cubic_overview,
    cubic_status,
    run_cubic_version,
)
from local_cli import route_query
from mcp_client.settings import CUBIC_MCP_URL, cubic_api_key, cubic_api_key_set

REPO_ROOT = Path(__file__).resolve().parents[4]
CURSOR_MCP_JSON = REPO_ROOT / ".cursor" / "mcp.json"
OVERVIEW_DOC = REPO_ROOT / "BitcoinAgent" / "CUBIC.md"


class CursorMcpConfigTests(unittest.TestCase):
    def test_project_mcp_json_points_at_hosted_cubic(self) -> None:
        config = json.loads(CURSOR_MCP_JSON.read_text(encoding="utf-8"))
        servers = config["mcpServers"]
        self.assertEqual(servers["cubic"]["url"], CUBIC_MCP_URL)
        self.assertEqual(CUBIC_MCP_URL, MCP_URL)
        self.assertEqual(servers["cubic"]["type"], "http")
        self.assertEqual(MCP_URL, "https://www.cubic.dev/api/mcp")
        self.assertNotIn("headers", servers["cubic"])
        dumped = json.dumps(config)
        self.assertNotIn("CUBIC_API_KEY", dumped)
        self.assertNotIn("cbk_", dumped)
        self.assertNotIn("https://cubic.dev/api/mcp", dumped)
        for name in WRITE_TOOLS:
            self.assertNotIn(name, dumped)


class CubicSettingsTests(unittest.TestCase):
    def test_disabled_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CUBIC_API_KEY", None)
            self.assertIsNone(cubic_api_key())
            self.assertFalse(cubic_api_key_set())

    def test_key_is_detected_not_printed(self) -> None:
        with patch.dict(os.environ, {"CUBIC_API_KEY": " cbk_test-key "}, clear=False):
            self.assertEqual(cubic_api_key(), "cbk_test-key")
            self.assertTrue(cubic_api_key_set())
            self.assertNotIn("cbk_test-key", cubic_status())


class CubicOverviewTests(unittest.TestCase):
    def test_overview_covers_mcp_and_refuses_writes(self) -> None:
        text = cubic_overview()
        lowered = text.lower()
        self.assertIn(MCP_URL, text)
        self.assertIn(MCP_DOCS_URL, text)
        self.assertIn("www.cubic.dev", text)
        self.assertIn("not attached", lowered)
        self.assertIn(CLI_INSTALL_CURL, text)
        self.assertIn(CLI_INSTALL_NPX, text)
        self.assertIn(CLI_PACKAGE, text)
        for name in WRITE_TOOLS:
            self.assertIn(name, text)

    def test_repo_overview_doc_exists(self) -> None:
        self.assertTrue(OVERVIEW_DOC.is_file())
        body = OVERVIEW_DOC.read_text(encoding="utf-8")
        self.assertIn(MCP_URL, body)
        self.assertIn("does **not** attach", body)
        self.assertIn("trigger_pr_review", body)
        self.assertIn("OAuth", body)
        self.assertIn("reject `https://cubic.dev/api/mcp`", body)
        self.assertGreater(body.count("https://www.cubic.dev/api/mcp"), 1)

    def test_howto_cubic_topic(self) -> None:
        text = developer_howto("cubic")
        self.assertIn("www.cubic.dev/api/mcp", text)
        self.assertEqual(developer_howto("cubic-mcp"), text)
        self.assertEqual(developer_howto("cubic.dev"), text)
        self.assertEqual(developer_howto("cubic-review"), text)
        self.assertIn("does not", text.lower())


class CubicStatusTests(unittest.TestCase):
    def test_status_without_key_or_cli(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CUBIC_API_KEY", None)
            with patch("cubic.cubic_cli_path", return_value=None):
                text = cubic_status()
        self.assertIn("unset", text.lower())
        self.assertIn(MCP_URL, text)
        self.assertIn("not attached", text.lower())
        self.assertIn(CLI_INSTALL_CURL, text)
        self.assertNotIn("cbk_", text)

    def test_version_is_read_only(self) -> None:
        class Completed:
            returncode = 0
            stdout = b"cubic 1.14.0\n"
            stderr = b""

        with patch("cubic.shutil.which", return_value="/usr/bin/cubic"):
            with patch("cubic.subprocess.run", return_value=Completed()) as mocked:
                payload = run_cubic_version()
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.args[0], ["/usr/bin/cubic", "--version"])
        self.assertEqual(payload, {"version": "cubic 1.14.0"})


class CubicLocalCliTests(unittest.TestCase):
    def test_routes_overview_and_status(self) -> None:
        overview = route_query("what is cubic mcp")
        self.assertIn(MCP_URL, overview)
        self.assertIn("trigger_pr_review", overview)
        status = route_query("cubic status")
        self.assertIn("CUBIC_API_KEY", status)
        self.assertIn("not attached", status.lower())

    def test_help_lists_cubic(self) -> None:
        text = route_query("help")
        self.assertIn("cubic", text)
        self.assertIn("status", text)

    def test_howto_route(self) -> None:
        text = route_query("howto cubic")
        self.assertIn("www.cubic.dev/api/mcp", text)
        self.assertIn("cubic review", text)


if __name__ == "__main__":
    unittest.main()
