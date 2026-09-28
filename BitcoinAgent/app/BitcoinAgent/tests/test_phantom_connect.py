from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bitcoin_tools import developer_howto
from local_cli import route_query
from mcp_client.settings import (
    PHANTOM_DOCS_MCP_URL,
    phantom_app_id,
    phantom_app_id_set,
    phantom_docs_mcp_enabled,
)
from phantom_connect import (
    BROWSER_INSTALL,
    CLI_INSTALL_COMMAND,
    DOCS_MCP_URL,
    GITHUB_URL,
    PACKAGES,
    REACT_INSTALL,
    WALLET_MCP_PACKAGE,
    npm_get_latest,
    npm_latest_path,
    phantom_cli_path,
    phantom_connect_cli_status,
    phantom_connect_overview,
    phantom_connect_packages,
    resolve_package_keys,
    run_phantom_version,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CURSOR_MCP_JSON = REPO_ROOT / ".cursor" / "mcp.json"
OVERVIEW_DOC = REPO_ROOT / "BitcoinAgent" / "PHANTOM.md"


class CursorMcpConfigTests(unittest.TestCase):
    def test_project_mcp_json_points_at_phantom_docs_only(self) -> None:
        config = json.loads(CURSOR_MCP_JSON.read_text(encoding="utf-8"))
        servers = config["mcpServers"]
        self.assertEqual(servers["phantom-docs"]["url"], PHANTOM_DOCS_MCP_URL)
        self.assertEqual(PHANTOM_DOCS_MCP_URL, DOCS_MCP_URL)
        self.assertNotIn("headers", servers["phantom-docs"])
        dumped = json.dumps(config)
        self.assertNotIn("@phantom/mcp-server", dumped)
        self.assertNotIn("PHANTOM_APP_ID", dumped)
        self.assertNotIn("phantom --mcp", dumped)


class PhantomSettingsTests(unittest.TestCase):
    def test_disabled_without_flag(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHANTOM_DOCS_MCP", None)
            os.environ.pop("PHANTOM_APP_ID", None)
            self.assertIsNone(phantom_app_id())
            self.assertFalse(phantom_app_id_set())
            self.assertFalse(phantom_docs_mcp_enabled())

    def test_docs_flag(self) -> None:
        with patch.dict(os.environ, {"PHANTOM_DOCS_MCP": "1"}, clear=False):
            self.assertTrue(phantom_docs_mcp_enabled())

    def test_app_id_is_detected_not_required_for_docs(self) -> None:
        with patch.dict(os.environ, {"PHANTOM_APP_ID": " test-app "}, clear=False):
            os.environ.pop("PHANTOM_DOCS_MCP", None)
            self.assertEqual(phantom_app_id(), "test-app")
            self.assertTrue(phantom_app_id_set())
            self.assertFalse(phantom_docs_mcp_enabled())


class PhantomOverviewTests(unittest.TestCase):
    def test_overview_covers_sdks_and_refuses_wallet_ops(self) -> None:
        text = phantom_connect_overview()
        lowered = text.lower()
        self.assertIn(GITHUB_URL, text)
        self.assertIn(REACT_INSTALL, text)
        self.assertIn(BROWSER_INSTALL, text)
        self.assertIn(CLI_INSTALL_COMMAND, text)
        self.assertIn(DOCS_MCP_URL, text)
        self.assertIn("phantom-docs", lowered)
        self.assertIn("does not attach", lowered)
        self.assertIn("does not connect a wallet", lowered)
        self.assertIn("signandsendtransaction", lowered)
        self.assertIn("@phantom/mcp-server", lowered)

    def test_repo_overview_doc_exists(self) -> None:
        self.assertTrue(OVERVIEW_DOC.is_file())
        body = OVERVIEW_DOC.read_text(encoding="utf-8")
        self.assertIn(GITHUB_URL, body)
        self.assertIn("does **not** connect a wallet", body)
        self.assertIn("@phantom/mcp-server", body)
        self.assertIn("phantom --version", body)

    def test_howto_phantom_topic(self) -> None:
        text = developer_howto("phantom")
        self.assertIn(CLI_INSTALL_COMMAND, text)
        self.assertIn(GITHUB_URL, text)
        self.assertEqual(developer_howto("phantom-connect"), text)
        self.assertEqual(developer_howto("phantom-docs"), text)
        self.assertEqual(developer_howto("react-sdk"), text)
        self.assertIn("PHANTOM_DOCS_MCP", text)


class PhantomPackageTests(unittest.TestCase):
    def test_resolves_aliases(self) -> None:
        self.assertEqual(resolve_package_keys(""), list(PACKAGES))
        self.assertEqual(resolve_package_keys("react"), ["react"])
        self.assertEqual(resolve_package_keys("@phantom/browser-sdk"), ["browser"])
        self.assertEqual(resolve_package_keys("rn, cli"), ["react-native", "cli"])

    def test_npm_path_is_latest_only(self) -> None:
        path = npm_latest_path("@phantom/react-sdk")
        self.assertEqual(path, "/@phantom/react-sdk/latest")
        with self.assertRaises(ValueError):
            npm_latest_path("@other/malware")

    def test_packages_formats_latest(self) -> None:
        payload = {
            "version": "1.2.3",
            "description": "React hooks for Phantom Connect",
            "license": "MIT",
            "homepage": "https://docs.phantom.com",
        }
        with patch("phantom_connect.npm_get_latest", return_value=payload) as mocked:
            text = phantom_connect_packages("react")
        mocked.assert_called_once_with("@phantom/react-sdk")
        self.assertIn("@phantom/react-sdk@1.2.3", text)
        self.assertIn("will not npm install", text.lower())

    def test_packages_refuses_wallet_mcp_fetch(self) -> None:
        text = phantom_connect_packages("mcp-server")
        self.assertIn(WALLET_MCP_PACKAGE, text)
        self.assertIn("does not attach", text.lower())

    def test_packages_unknown(self) -> None:
        text = phantom_connect_packages("left-pad")
        self.assertIn("Unknown Phantom package", text)

    def test_packages_refuses_secrets(self) -> None:
        self.assertIn("seed", phantom_connect_packages("my seed phrase apple").lower())

    def test_npm_get_allowlist(self) -> None:
        with self.assertRaises(ValueError):
            npm_get_latest("@evil/pkg")

    def test_npm_get_uses_https_latest(self) -> None:
        class FakeResponse:
            status = 200

            def read(self, _n: int) -> bytes:
                return json.dumps({"version": "9.9.9", "name": "@phantom/cli"}).encode()

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        with patch("phantom_connect.urllib.request.urlopen", return_value=FakeResponse()) as mocked:
            result = npm_get_latest("@phantom/cli")
        self.assertEqual(result["version"], "9.9.9")
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://registry.npmjs.org/@phantom/cli/latest")
        self.assertEqual(request.get_method(), "GET")


class PhantomCliStatusTests(unittest.TestCase):
    def test_missing_cli(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHANTOM_APP_ID", None)
            os.environ.pop("PHANTOM_DOCS_MCP", None)
            with patch("phantom_connect.phantom_cli_path", return_value=None):
                text = phantom_connect_cli_status()
        self.assertIn("not found", text.lower())
        self.assertIn(CLI_INSTALL_COMMAND, text)
        self.assertIn("will not run login", text.lower())
        self.assertNotIn("secret", text.lower())

    def test_version_only(self) -> None:
        with patch("phantom_connect.phantom_cli_path", return_value="/usr/bin/phantom"):
            with patch("phantom_connect.run_phantom_version", return_value={"version": "0.2.0"}):
                with patch.dict(os.environ, {"PHANTOM_APP_ID": "super-secret-app-id"}):
                    text = phantom_connect_cli_status()
        self.assertIn("0.2.0", text)
        self.assertIn("PHANTOM_APP_ID: set", text)
        self.assertNotIn("super-secret-app-id", text)
        self.assertIn("only checks the version", text.lower())

    def test_run_version_argv(self) -> None:
        class Result:
            returncode = 0
            stdout = b"0.2.0\n"
            stderr = b""

        with patch("phantom_connect.subprocess.run", return_value=Result()) as mocked:
            payload = run_phantom_version("/opt/phantom")
        mocked.assert_called_once()
        args = mocked.call_args.args[0]
        self.assertEqual(args, ["/opt/phantom", "--version"])
        self.assertEqual(payload["version"], "0.2.0")

    def test_which_helper_exists(self) -> None:
        self.assertTrue(callable(phantom_cli_path))


class PhantomLocalCliTests(unittest.TestCase):
    def test_routes_overview_packages_status(self) -> None:
        overview = route_query("what is phantom connect sdk")
        self.assertIn(GITHUB_URL, overview)
        self.assertIn(CLI_INSTALL_COMMAND, overview)
        with patch(
            "phantom_connect.npm_get_latest",
            return_value={"version": "1.0.0", "description": "demo"},
        ):
            packages = route_query("phantom packages react")
        self.assertIn("@phantom/react-sdk@1.0.0", packages)
        with patch("phantom_connect.phantom_cli_path", return_value=None):
            status = route_query("phantom status")
        self.assertIn("not found", status.lower())

    def test_help_lists_phantom(self) -> None:
        text = route_query("help")
        self.assertIn("phantom", text)
        self.assertIn("packages", text)

    def test_howto_route(self) -> None:
        text = route_query("howto phantom")
        self.assertIn(GITHUB_URL, text)
        self.assertIn("PHANTOM_DOCS_MCP", text)

    def test_natural_language_packages(self) -> None:
        with patch(
            "phantom_connect.npm_get_latest",
            return_value={"version": "2.0.0", "description": "Browser SDK"},
        ):
            text = route_query("phantom connect npm package for browser-sdk")
        self.assertIn("@phantom/browser-sdk@2.0.0", text)


if __name__ == "__main__":
    unittest.main()
