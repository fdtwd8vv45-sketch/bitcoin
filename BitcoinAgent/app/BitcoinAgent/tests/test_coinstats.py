from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bitcoin_tools import developer_howto
from coinstats import (
    DASHBOARD_URL,
    MCP_URL,
    STDIO_COMMAND,
    allowed_coinstats_path,
    coinstats_coin,
    coinstats_get,
    coinstats_markets,
    coinstats_overview,
    coinstats_portfolio,
    coinstats_portfolio_list,
    coinstats_status,
    coinstats_wallet,
    resolve_coin_id,
    resolve_portfolio_id,
    resolve_wallet_chain,
)
from local_cli import route_query
from mcp_client.settings import (
    COINSTATS_MCP_URL,
    coinstats_api_key,
    coinstats_api_key_set,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CURSOR_MCP_JSON = REPO_ROOT / ".cursor" / "mcp.json"
OVERVIEW_DOC = REPO_ROOT / "BitcoinAgent" / "COINSTATS.md"


class CursorMcpConfigTests(unittest.TestCase):
    def test_project_mcp_json_points_at_hosted_coinstats(self) -> None:
        config = json.loads(CURSOR_MCP_JSON.read_text(encoding="utf-8"))
        servers = config["mcpServers"]
        self.assertEqual(servers["coinstats"]["url"], COINSTATS_MCP_URL)
        self.assertEqual(COINSTATS_MCP_URL, MCP_URL)
        self.assertNotIn("headers", servers["coinstats"])
        dumped = json.dumps(config)
        self.assertNotIn("COINSTATS_API_KEY", dumped)
        self.assertNotIn("@coinstats/coinstats-mcp", dumped)
        self.assertNotIn("delete-portfolio", dumped)


class CoinStatsSettingsTests(unittest.TestCase):
    def test_disabled_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COINSTATS_API_KEY", None)
            self.assertIsNone(coinstats_api_key())
            self.assertFalse(coinstats_api_key_set())

    def test_key_is_detected_not_printed(self) -> None:
        with patch.dict(os.environ, {"COINSTATS_API_KEY": " test-key "}, clear=False):
            self.assertEqual(coinstats_api_key(), "test-key")
            self.assertTrue(coinstats_api_key_set())
            self.assertNotIn("test-key", coinstats_status())


class CoinStatsOverviewTests(unittest.TestCase):
    def test_overview_covers_mcp_and_refuses_writes(self) -> None:
        text = coinstats_overview()
        lowered = text.lower()
        self.assertIn(MCP_URL, text)
        self.assertIn(DASHBOARD_URL, text)
        self.assertIn("llms.txt", lowered)
        self.assertIn("not attached", lowered)
        self.assertIn("delete-portfolio", lowered)
        self.assertIn("add-portfolio-transaction", lowered)
        self.assertIn(STDIO_COMMAND, text)

    def test_repo_overview_doc_exists(self) -> None:
        self.assertTrue(OVERVIEW_DOC.is_file())
        body = OVERVIEW_DOC.read_text(encoding="utf-8")
        self.assertIn(MCP_URL, body)
        self.assertIn("does **not** add", body)
        self.assertIn("delete-portfolio", body)
        self.assertIn("OAuth", body)

    def test_howto_coinstats_topic(self) -> None:
        text = developer_howto("coinstats")
        self.assertIn("mcp.coinstats.app", text)
        self.assertEqual(developer_howto("coin-stats"), text)
        self.assertEqual(developer_howto("coinstats-mcp"), text)
        self.assertEqual(developer_howto("coinstats-portfolio"), text)
        self.assertIn("COINSTATS_API_KEY", text)
        self.assertIn("does not add", text.lower())


class CoinStatsResolveTests(unittest.TestCase):
    def test_resolves_known_symbols_and_slugs(self) -> None:
        self.assertEqual(resolve_coin_id("BTC"), "bitcoin")
        self.assertEqual(resolve_coin_id("ethereum"), "ethereum")
        self.assertEqual(resolve_coin_id("USDC"), "usd-coin")
        self.assertEqual(resolve_coin_id("solana"), "solana")

    def test_skips_stopwords_and_secrets(self) -> None:
        self.assertIsNone(resolve_coin_id("price"))
        self.assertIsNone(resolve_coin_id("my seed phrase"))
        self.assertIsNone(resolve_portfolio_id("share token abc"))
        self.assertEqual(resolve_portfolio_id("all"), "")
        self.assertEqual(resolve_portfolio_id("abc123"), "abc123")

    def test_wallet_chain_rejects_all(self) -> None:
        self.assertIsNone(resolve_wallet_chain("all"))
        self.assertIsNone(resolve_wallet_chain("forceall"))
        self.assertEqual(resolve_wallet_chain("bitcoin"), "bitcoin")
        self.assertEqual(resolve_wallet_chain("solana"), "solana")


class CoinStatsHttpTests(unittest.TestCase):
    def test_allowlist_blocks_write_paths(self) -> None:
        self.assertTrue(allowed_coinstats_path("/v1/coins"))
        self.assertTrue(allowed_coinstats_path("/v1/coins/bitcoin"))
        self.assertTrue(allowed_coinstats_path("/v1/portfolio/list"))
        self.assertTrue(allowed_coinstats_path("/v1/wallet/balance"))
        self.assertFalse(allowed_coinstats_path("/v1/coins/bitcoin/chart"))
        self.assertFalse(allowed_coinstats_path("/v1/portfolio"))
        self.assertFalse(allowed_coinstats_path("/v1/portfolio/transaction"))
        self.assertFalse(allowed_coinstats_path("/v1/wallet/transactions"))
        with self.assertRaises(ValueError):
            coinstats_get("/v1/portfolio/transaction", {"portfolioId": "x"})
        with self.assertRaises(ValueError):
            coinstats_get("/v1/coins/bitcoin/chart")

    def test_sends_api_key_header_without_leaking_it(self) -> None:
        payload = json.dumps({"id": "bitcoin", "price": 1}).encode()

        class FakeResponse:
            status = 200

            def read(self, _n: int) -> bytes:
                return payload

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        with patch.dict(os.environ, {"COINSTATS_API_KEY": "secret-cs-key"}):
            with patch("coinstats.urllib.request.urlopen", return_value=FakeResponse()) as mocked:
                result = coinstats_get("/v1/coins/bitcoin", {"currency": "USD"})
            request = mocked.call_args.args[0]
        header_map = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(header_map.get("x-api-key"), "secret-cs-key")
        dumped = json.dumps(result)
        self.assertNotIn("secret-cs-key", dumped)


class CoinStatsToolTests(unittest.TestCase):
    def test_coin_formats_payload(self) -> None:
        payload = {
            "id": "bitcoin",
            "name": "Bitcoin",
            "symbol": "BTC",
            "price": 100_000.5,
            "priceChange1h": 0.2,
            "priceChange1d": -1.5,
            "priceChange1w": 3.0,
            "marketCap": 2_000_000_000_000,
            "volume": 40_000_000_000,
            "rank": 1,
        }
        with patch.dict(os.environ, {"COINSTATS_API_KEY": "k"}, clear=False):
            with patch("coinstats.coinstats_get", return_value=payload) as mocked:
                text = coinstats_coin("BTC")
        mocked.assert_called_once_with("/v1/coins/bitcoin", {"currency": "USD"})
        self.assertIn("100,000.5", text)
        self.assertIn("-1.50%", text)
        self.assertIn("will not trade", text.lower())

    def test_coin_requires_key_and_rejects_secrets(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COINSTATS_API_KEY", None)
            text = coinstats_coin("bitcoin")
        self.assertIn("COINSTATS_API_KEY", text)
        self.assertIn("seed", coinstats_coin("my seed phrase apple").lower())
        self.assertIn("bitcoin", coinstats_coin(""))

    def test_markets_formats_payload(self) -> None:
        payload = {
            "marketCap": 4_000_000_000_000,
            "volume": 100_000_000_000,
            "btcDominance": 54.2,
            "marketCapChange": 1.1,
            "volumeChange": -2.0,
            "btcDominanceChange": 0.3,
        }
        with patch.dict(os.environ, {"COINSTATS_API_KEY": "k"}, clear=False):
            with patch("coinstats.coinstats_get", return_value=payload):
                text = coinstats_markets()
        self.assertIn("54.2", text)
        self.assertIn("+1.10%", text)

    def test_portfolio_list_and_coins(self) -> None:
        listing = {
            "result": [
                {
                    "portfolioId": "abc123",
                    "portfolioName": "Main",
                    "portfolioType": "wallet",
                }
            ]
        }
        coins = {
            "result": [
                {
                    "count": 1.5,
                    "coin": {"symbol": "BTC", "name": "Bitcoin"},
                    "price": {"USD": 100000},
                    "profit": {"unrealized": {"USD": 2500}},
                    "profitPercent": {"unrealized": {"USD": 12.5}},
                }
            ]
        }
        with patch.dict(os.environ, {"COINSTATS_API_KEY": "k"}, clear=False):
            with patch("coinstats.coinstats_get", return_value=listing) as mocked:
                listed = coinstats_portfolio_list()
            mocked.assert_called_once_with("/v1/portfolio/list")
            with patch("coinstats.coinstats_get", return_value=coins) as mocked_coins:
                holdings = coinstats_portfolio("abc123")
            mocked_coins.assert_called_once_with(
                "/v1/portfolio/coins",
                {"limit": "20", "page": "1", "portfolioId": "abc123"},
            )
        self.assertIn("abc123", listed)
        self.assertIn("Main", listed)
        self.assertIn("BTC", holdings)
        self.assertIn("uPnL", holdings)
        self.assertIn("will not add", holdings.lower())

    def test_wallet_defaults_bitcoin_and_blocks_all(self) -> None:
        address = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
        payload = [
            {
                "symbol": "BTC",
                "name": "Bitcoin",
                "amount": 0.1,
                "price": 100000,
                "pCh24h": 1.2,
            }
        ]
        with patch.dict(os.environ, {"COINSTATS_API_KEY": "k"}, clear=False):
            with patch("coinstats.coinstats_get", return_value=payload) as mocked:
                text = coinstats_wallet(address)
            mocked.assert_called_once()
            self.assertEqual(mocked.call_args.args[0], "/v1/wallet/balance")
            self.assertEqual(mocked.call_args.args[1]["blockchain"], "bitcoin")
            blocked = coinstats_wallet(address, "all")
        self.assertIn("0.1", text)
        self.assertIn("will not send", text.lower())
        self.assertIn("forceall", blocked.lower())

    def test_wallet_rejects_secrets(self) -> None:
        self.assertIn("seed", coinstats_wallet("xprv123").lower())

    def test_status_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COINSTATS_API_KEY", None)
            text = coinstats_status()
        self.assertIn("unset", text.lower())
        self.assertIn(MCP_URL, text)
        self.assertIn("not attached", text.lower())


class CoinStatsLocalCliTests(unittest.TestCase):
    def test_routes_overview_coin_portfolio_status(self) -> None:
        overview = route_query("what is coinstats mcp")
        self.assertIn(MCP_URL, overview)
        payload = {
            "id": "bitcoin",
            "name": "Bitcoin",
            "symbol": "BTC",
            "price": 99.0,
            "priceChange1h": 0,
            "priceChange1d": 0,
            "priceChange1w": 0,
            "marketCap": 1,
            "volume": 1,
            "rank": 1,
        }
        with patch.dict(os.environ, {"COINSTATS_API_KEY": "k"}, clear=False):
            with patch("coinstats.coinstats_get", return_value=payload):
                price = route_query("coinstats coin bitcoin")
            listing = {"result": [{"portfolioId": "p1", "portfolioName": "Watch", "portfolioType": "manual"}]}
            with patch("coinstats.coinstats_get", return_value=listing):
                listed = route_query("coinstats portfolio list")
        self.assertIn("99", price)
        self.assertIn("p1", listed)
        status = route_query("coinstats status")
        self.assertIn("COINSTATS_API_KEY", status)

    def test_help_lists_coinstats(self) -> None:
        text = route_query("help")
        self.assertIn("coinstats", text)
        self.assertIn("portfolio", text)

    def test_howto_route(self) -> None:
        text = route_query("howto coinstats")
        self.assertIn("mcp.coinstats.app", text)
        self.assertIn("COINSTATS_API_KEY", text)


if __name__ == "__main__":
    unittest.main()
