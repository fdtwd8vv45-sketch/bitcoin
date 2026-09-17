from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bitcoin_tools import developer_howto
from jupiter import (
    DOCS_MCP_URL,
    INSTALL_COMMAND,
    KNOWN_MINTS,
    jup_cli_path,
    jupiter_cli_status,
    jupiter_get,
    jupiter_overview,
    jupiter_price,
    jupiter_token_search,
    resolve_price_id,
    resolve_price_ids,
    run_jup_version,
)
from local_cli import route_query
from mcp_client.settings import (
    JUPITER_DOCS_MCP_URL,
    jupiter_api_key,
    jupiter_docs_mcp_enabled,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CURSOR_MCP_JSON = REPO_ROOT / ".cursor" / "mcp.json"
OVERVIEW_DOC = REPO_ROOT / "BitcoinAgent" / "JUPITER.md"
SOL = KNOWN_MINTS["sol"]
JUP = KNOWN_MINTS["jup"]


class CursorMcpConfigTests(unittest.TestCase):
    def test_project_mcp_json_points_at_jupiter_docs_only(self) -> None:
        config = json.loads(CURSOR_MCP_JSON.read_text(encoding="utf-8"))
        servers = config["mcpServers"]
        self.assertEqual(servers["jupiter-docs"]["url"], JUPITER_DOCS_MCP_URL)
        self.assertEqual(JUPITER_DOCS_MCP_URL, DOCS_MCP_URL)
        self.assertNotIn("headers", servers["jupiter-docs"])
        dumped = json.dumps(config)
        self.assertNotIn("mcp.jup.ag", dumped)
        self.assertNotIn("YOUR_JUPITER_API_KEY", dumped)
        self.assertNotIn("jup_", dumped)


class JupiterSettingsTests(unittest.TestCase):
    def test_disabled_without_flag_or_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JUPITER_API_KEY", None)
            os.environ.pop("JUPITER_DOCS_MCP", None)
            self.assertIsNone(jupiter_api_key())
            self.assertFalse(jupiter_docs_mcp_enabled())

    def test_key_enables_docs_mcp(self) -> None:
        with patch.dict(os.environ, {"JUPITER_API_KEY": " test-key "}, clear=False):
            os.environ.pop("JUPITER_DOCS_MCP", None)
            self.assertEqual(jupiter_api_key(), "test-key")
            self.assertTrue(jupiter_docs_mcp_enabled())

    def test_docs_only_flag(self) -> None:
        with patch.dict(os.environ, {"JUPITER_DOCS_MCP": "1"}, clear=False):
            os.environ.pop("JUPITER_API_KEY", None)
            self.assertIsNone(jupiter_api_key())
            self.assertTrue(jupiter_docs_mcp_enabled())


class JupiterOverviewTests(unittest.TestCase):
    def test_overview_covers_ai_tools_and_refuses_trading(self) -> None:
        text = jupiter_overview()
        lowered = text.lower()
        self.assertIn("llms.txt", lowered)
        self.assertIn(INSTALL_COMMAND, text)
        self.assertIn("integrating-jupiter", text)
        self.assertIn(DOCS_MCP_URL, text)
        self.assertIn("does not swap", lowered)
        self.assertIn("jupiter-docs", lowered)

    def test_repo_overview_doc_exists(self) -> None:
        self.assertTrue(OVERVIEW_DOC.is_file())
        body = OVERVIEW_DOC.read_text(encoding="utf-8")
        self.assertIn("llms.txt", body)
        self.assertIn(INSTALL_COMMAND, body)
        self.assertIn("does **not** swap", body)

    def test_howto_jupiter_topic(self) -> None:
        text = developer_howto("jupiter")
        self.assertIn(INSTALL_COMMAND, text)
        self.assertIn("llms.txt", text)
        self.assertEqual(developer_howto("jup"), text)
        self.assertEqual(developer_howto("jupiter-docs"), text)


class JupiterPriceTests(unittest.TestCase):
    def test_resolves_known_symbols_and_mints(self) -> None:
        self.assertEqual(resolve_price_id("SOL"), SOL)
        self.assertEqual(resolve_price_id("jup"), JUP)
        self.assertEqual(resolve_price_id(SOL), SOL)
        ids, unknown = resolve_price_ids("SOL, JUP")
        self.assertEqual(ids, [SOL, JUP])
        self.assertEqual(unknown, [])

    def test_skips_stopwords(self) -> None:
        ids, unknown = resolve_price_ids("price of SOL on jupiter")
        self.assertEqual(ids, [SOL])
        self.assertEqual(unknown, [])

    def test_price_formats_payload(self) -> None:
        payload = {
            SOL: {"usdPrice": 100.5, "priceChange24h": 1.25, "decimals": 9, "blockId": 12},
            JUP: {"usdPrice": 0.2, "priceChange24h": -0.5, "decimals": 6, "blockId": 13},
        }
        with patch("jupiter.jupiter_get", return_value=payload) as mocked:
            text = jupiter_price("SOL,JUP")
        mocked.assert_called_once_with("/price/v3", {"ids": f"{SOL},{JUP}"})
        self.assertIn("100.5", text)
        self.assertIn("+1.25%", text)
        self.assertIn("-0.50%", text)
        self.assertIn("will not swap", text.lower())

    def test_price_empty_usage(self) -> None:
        self.assertIn("SOL,JUP", jupiter_price(""))

    def test_price_rejects_secrets(self) -> None:
        self.assertIn("seed", jupiter_price("my seed phrase apple").lower())

    def test_price_omitted_mint(self) -> None:
        with patch("jupiter.jupiter_get", return_value={}):
            text = jupiter_price("SOL")
        self.assertIn("no reliable price", text.lower())

    def test_unknown_symbol_uses_verified_search_hit(self) -> None:
        mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"

        def fake_get(path: str, query: dict[str, str]) -> object:
            if path == "/tokens/v2/search":
                return [
                    {"id": "scamMint11111111111111111111111111111111111", "isVerified": False, "symbol": "BONK"},
                    {"id": mint, "isVerified": True, "symbol": "BONK"},
                ]
            self.assertEqual(path, "/price/v3")
            self.assertEqual(query["ids"], mint)
            return {mint: {"usdPrice": 0.00002, "priceChange24h": 3.0, "decimals": 5, "blockId": 9}}

        with patch("jupiter.jupiter_get", side_effect=fake_get):
            text = jupiter_price("BONK")
        self.assertIn(mint, text)
        self.assertIn("+3.00%", text)
        self.assertNotIn("scamMint", text)


class JupiterTokenSearchTests(unittest.TestCase):
    def test_formats_verified_hit_and_truncates(self) -> None:
        hits = [
            {
                "id": JUP,
                "name": "Jupiter",
                "symbol": "JUP",
                "isVerified": True,
                "organicScore": 98.08,
                "organicScoreLabel": "high",
                "usdPrice": 0.2,
                "mcap": 461_000_000,
                "holderCount": 800_000,
                "tags": ["verified", "community"],
                "audit": {"isSus": True},
            }
        ]
        hits.extend({"id": f"mint{i}", "name": f"Copy {i}", "symbol": "JUP"} for i in range(10))
        with patch("jupiter.jupiter_get", return_value=hits):
            text = jupiter_token_search("JUP")
        self.assertIn(JUP, text)
        self.assertIn("verified", text)
        self.assertIn("suspicious", text)
        self.assertIn("organic 98.1 high", text)
        self.assertIn("more hits omitted", text)
        self.assertNotIn("mint9", text)

    def test_empty_search(self) -> None:
        with patch("jupiter.jupiter_get", return_value=[]):
            text = jupiter_token_search("zzz-not-a-token")
        self.assertIn("No Jupiter tokens matched", text)

    def test_search_rejects_secrets(self) -> None:
        self.assertIn("seed", jupiter_token_search("private key").lower())


class JupiterHttpTests(unittest.TestCase):
    def test_allowlist_blocks_other_paths(self) -> None:
        with self.assertRaises(ValueError):
            jupiter_get("/swap/v2/order", {"inputMint": SOL})

    def test_sends_api_key_header_without_leaking_it(self) -> None:
        payload = json.dumps({SOL: {"usdPrice": 1}}).encode()

        class FakeResponse:
            status = 200

            def read(self, _n: int) -> bytes:
                return payload

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        with patch.dict(os.environ, {"JUPITER_API_KEY": "secret-jup-key"}):
            with patch("jupiter.urllib.request.urlopen", return_value=FakeResponse()) as mocked:
                result = jupiter_get("/price/v3", {"ids": SOL})
            request = mocked.call_args.args[0]
        header_map = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(header_map.get("x-api-key"), "secret-jup-key")
        dumped = json.dumps(result)
        self.assertNotIn("secret-jup-key", dumped)


class JupiterCliStatusTests(unittest.TestCase):
    def test_status_without_cli(self) -> None:
        with patch("jupiter.jup_cli_path", return_value=None):
            text = jupiter_cli_status()
        self.assertIn("not found", text.lower())
        self.assertIn(INSTALL_COMMAND, text)
        self.assertIn("will not run swap", text.lower())

    def test_status_with_version(self) -> None:
        with patch("jupiter.jup_cli_path", return_value="/usr/bin/jup"):
            with patch("jupiter.run_jup_version", return_value={"version": "0.4.0"}):
                text = jupiter_cli_status()
        self.assertIn("/usr/bin/jup", text)
        self.assertIn("0.4.0", text)
        self.assertNotIn("swap SOL", text)

    def test_run_jup_version_uses_version_argv_only(self) -> None:
        class Result:
            returncode = 0
            stdout = b"0.4.0\n"
            stderr = b""

        with patch("jupiter.subprocess.run", return_value=Result()) as mocked:
            payload = run_jup_version("/opt/jup")
        mocked.assert_called_once()
        args = mocked.call_args.args[0]
        self.assertEqual(args, ["/opt/jup", "--version"])
        self.assertEqual(payload["version"], "0.4.0")

    def test_which_helper_exists(self) -> None:
        self.assertTrue(callable(jup_cli_path))


class JupiterLocalCliTests(unittest.TestCase):
    def test_routes_overview_price_token_status(self) -> None:
        overview = route_query("what is jupiter api")
        self.assertIn("llms.txt", overview.lower())
        self.assertIn(INSTALL_COMMAND, overview)
        with patch("jupiter.jupiter_get", return_value={SOL: {"usdPrice": 99.0, "priceChange24h": 0.0, "decimals": 9}}):
            price = route_query("jupiter price SOL")
        self.assertIn("99", price)
        with patch("jupiter.jupiter_get", return_value=[{"id": JUP, "name": "Jupiter", "symbol": "JUP", "isVerified": True}]):
            search = route_query("jupiter token JUP")
        self.assertIn(JUP, search)
        with patch("jupiter.jup_cli_path", return_value=None):
            status = route_query("jupiter status")
        self.assertIn("not found", status.lower())

    def test_help_lists_jupiter(self) -> None:
        text = route_query("help")
        self.assertIn("jupiter", text)

    def test_natural_language_price(self) -> None:
        with patch("jupiter.jupiter_get", return_value={JUP: {"usdPrice": 0.4, "priceChange24h": 1.0, "decimals": 6}}):
            text = route_query("what is the jupiter price of JUP")
        self.assertIn("0.4", text)


if __name__ == "__main__":
    unittest.main()
