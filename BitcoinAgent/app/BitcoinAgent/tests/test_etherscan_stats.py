from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bitcoin_tools import developer_howto
from etherscan_stats import (
    BUILD_WITH_AI_URL,
    CHARTS_URL,
    CLI_PACKAGE,
    KEY_URL,
    MCP_URL,
    SHOWCASE_URL,
    allowed_stats_action,
    etherscan_eth_price,
    etherscan_eth_supply,
    etherscan_gas_oracle,
    etherscan_node_count,
    etherscan_stats,
    etherscan_stats_from_arg,
    etherscan_stats_get,
    etherscan_stats_overview,
    etherscan_stats_status,
)
from local_cli import route_query

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERVIEW_DOC = REPO_ROOT / "BitcoinAgent" / "ETHERSCAN_STATS.md"

_SUPPLY2 = {
    "EthSupply": "122373866217800000000000000",
    "Eth2Staking": "2940327167090033000000000",
    "BurntFees": "4610942856337430575173814",
    "WithdrawnTotal": "7618584348954597000000000",
}
_PRICE = {
    "ethbtc": "0.0368322132423383",
    "ethbtc_timestamp": "1759139509",
    "ethusd": "4129.30651044757",
    "ethusd_timestamp": "1759139509",
}
_NODES = {"UTCDate": "2025-09-25", "TotalNodeCount": "11786"}
_GAS = {
    "LastBlock": "23467872",
    "SafeGasPrice": "0.496839934",
    "ProposeGasPrice": "0.496840168",
    "FastGasPrice": "0.55411917",
    "suggestBaseFee": "0.496839934",
    "gasUsedRatio": "0.405942555555556,0.784013777777778",
}


def _ok(result: object) -> dict:
    return {"status": "1", "message": "OK", "result": result}


class EtherscanStatsOverviewTests(unittest.TestCase):
    def test_overview_covers_free_tier_and_refuses_pro(self) -> None:
        text = etherscan_stats_overview()
        lowered = text.lower()
        self.assertIn(CHARTS_URL, text)
        self.assertIn(MCP_URL, text)
        self.assertIn(BUILD_WITH_AI_URL, text)
        self.assertIn(CLI_PACKAGE, text)
        self.assertIn("ethsupply2", lowered)
        self.assertIn("dailytx", lowered)
        self.assertIn("does not call", lowered)

    def test_repo_overview_doc_exists(self) -> None:
        self.assertTrue(OVERVIEW_DOC.is_file())
        body = OVERVIEW_DOC.read_text(encoding="utf-8")
        self.assertIn(CHARTS_URL, body)
        self.assertIn("does **not**", body)
        self.assertIn("dailytx", body)
        self.assertIn("ETHERSCAN_API_KEY", body)

    def test_howto_etherscan_stats_topic(self) -> None:
        text = developer_howto("etherscan-stats")
        self.assertIn("etherscan.io/charts", text)
        self.assertEqual(developer_howto("ethstats"), text)
        self.assertEqual(developer_howto("etherscan-statistics"), text)
        self.assertIn("ETHERSCAN_API_KEY", text)
        self.assertIn("does not call PRO", text)


class EtherscanStatsAllowlistTests(unittest.TestCase):
    def test_allowlist_blocks_pro_and_writes(self) -> None:
        self.assertTrue(allowed_stats_action("stats", "ethsupply2"))
        self.assertTrue(allowed_stats_action("stats", "ethprice"))
        self.assertTrue(allowed_stats_action("stats", "nodecount"))
        self.assertTrue(allowed_stats_action("gastracker", "gasoracle"))
        self.assertFalse(allowed_stats_action("stats", "dailytx"))
        self.assertFalse(allowed_stats_action("proxy", "eth_sendRawTransaction"))
        with self.assertRaises(ValueError):
            etherscan_stats_get("1", "stats", "dailytx")
        with self.assertRaises(ValueError):
            etherscan_stats_get("1", "proxy", "eth_sendRawTransaction")


class EtherscanStatsToolTests(unittest.TestCase):
    def test_missing_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ETHERSCAN_API_KEY", None)
            text = etherscan_eth_supply()
        self.assertIn("ETHERSCAN_API_KEY", text)
        self.assertIn(KEY_URL, text)
        self.assertNotIn("apikey=", text.lower())

    def test_rejects_secrets_and_bad_chain(self) -> None:
        self.assertIn("seed", etherscan_eth_price("my seed phrase apple").lower())
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "k"}, clear=False):
            self.assertIn("chainid must be", etherscan_node_count("nope"))

    def test_supply_formats_ethsupply2(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "k"}, clear=False):
            with patch(
                "etherscan_stats.etherscan_stats_get",
                return_value=_ok(_SUPPLY2),
            ) as mocked:
                text = etherscan_eth_supply("ethereum")
        mocked.assert_called_once_with("1", "stats", "ethsupply2")
        self.assertIn("122,373,866.2178", text)
        self.assertIn("Eth2Staking", text)
        self.assertIn("BurntFees", text)
        self.assertIn("will not send", text.lower())

    def test_price_formats_and_timestamp(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "k"}, clear=False):
            with patch(
                "etherscan_stats.etherscan_stats_get",
                return_value=_ok(_PRICE),
            ) as mocked:
                text = etherscan_eth_price("1")
        mocked.assert_called_once_with("1", "stats", "ethprice")
        self.assertIn("4,129.3065", text)
        self.assertIn("0.03683221", text)
        self.assertIn("2025-09-29", text)
        self.assertIn("will not trade", text.lower())

    def test_nodes_and_gas(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "k"}, clear=False):
            with patch(
                "etherscan_stats.etherscan_stats_get",
                return_value=_ok(_NODES),
            ):
                nodes = etherscan_node_count("base")
            with patch(
                "etherscan_stats.etherscan_stats_get",
                return_value=_ok(_GAS),
            ) as mocked:
                gas = etherscan_gas_oracle("arbitrum")
        self.assertIn("11,786", nodes)
        self.assertIn("2025-09-25", nodes)
        self.assertIn("8453", nodes)
        mocked.assert_called_once_with("42161", "gastracker", "gasoracle")
        self.assertIn("0.49683993", gas)
        self.assertIn("23467872", gas)
        self.assertIn("will not send", gas.lower())

    def test_snapshot_collects_four_sections(self) -> None:
        payloads = {
            ("stats", "ethsupply2"): _ok(_SUPPLY2),
            ("stats", "ethprice"): _ok(_PRICE),
            ("stats", "nodecount"): _ok(_NODES),
            ("gastracker", "gasoracle"): _ok(_GAS),
        }

        def fake_get(chain_id: str, module: str, action: str) -> dict:
            self.assertEqual(chain_id, "1")
            return payloads[(module, action)]

        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "k"}, clear=False):
            with patch("etherscan_stats.etherscan_stats_get", side_effect=fake_get):
                text = etherscan_stats()
        self.assertIn("## supply", text)
        self.assertIn("## price", text)
        self.assertIn("## nodes", text)
        self.assertIn("## gas", text)
        self.assertIn(CHARTS_URL, text)
        self.assertIn("PRO daily", text)

    def test_status_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ETHERSCAN_API_KEY", None)
            text = etherscan_stats_status()
        self.assertIn("unset", text.lower())
        self.assertIn(MCP_URL, text)
        self.assertNotIn("k-secret", text)

    def test_status_does_not_print_key(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "k-secret"}, clear=False):
            text = etherscan_stats_status()
        self.assertIn("set", text.lower())
        self.assertNotIn("k-secret", text)


class EtherscanStatsLocalCliTests(unittest.TestCase):
    def test_routes_overview_snapshot_status(self) -> None:
        overview = route_query("etherscan-stats")
        self.assertIn(CHARTS_URL, overview)
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "k"}, clear=False):
            with patch(
                "etherscan_stats.etherscan_stats_get",
                return_value=_ok(_PRICE),
            ):
                price = route_query("etherscan-stats price")
            with patch(
                "etherscan_stats.etherscan_stats_get",
                return_value=_ok(_SUPPLY2),
            ):
                supply = route_query("ethstats supply arbitrum")
        self.assertIn("4,129.3065", price)
        self.assertIn("42161", supply)
        status = route_query("etherscan-stats status")
        self.assertIn("ETHERSCAN_API_KEY", status)

    def test_natural_language(self) -> None:
        text = route_query("what are etherscan stats")
        self.assertIn(CHARTS_URL, text)
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "k"}, clear=False):
            with patch(
                "etherscan_stats.etherscan_stats_get",
                return_value=_ok(_NODES),
            ):
                nodes = route_query("etherscan node count")
        self.assertIn("11,786", nodes)

    def test_refuses_pro_and_source_addresses(self) -> None:
        pro = route_query("etherscan-stats dailytx")
        self.assertIn("PRO", pro)
        self.assertIn(SHOWCASE_URL, pro)
        source = etherscan_stats_from_arg(
            "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        )
        self.assertIn("source <0xaddress>", source)

    def test_help_lists_etherscan_stats(self) -> None:
        text = route_query("help")
        self.assertIn("etherscan-stats", text)
        self.assertIn("snapshot", text)

    def test_howto_route(self) -> None:
        text = route_query("howto etherscan-stats")
        self.assertIn("etherscan.io/charts", text)
        self.assertIn("ETHERSCAN_API_KEY", text)

    def test_from_arg_helpers(self) -> None:
        self.assertIn(CHARTS_URL, etherscan_stats_from_arg(""))
        self.assertIn("ETHERSCAN_API_KEY", etherscan_stats_from_arg("status"))
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "k"}, clear=False):
            with patch(
                "etherscan_stats.etherscan_stats_get",
                return_value=_ok(_GAS),
            ):
                gas = etherscan_stats_from_arg("gas base")
        self.assertIn("8453", gas)

    def test_source_and_execution_still_work(self) -> None:
        text = route_query("rpc getblockcount")
        self.assertIn("RPC: getblockcount", text)
        self.assertNotIn("Etherscan ETH", text)
        execution = route_query("eth_blockNumber")
        self.assertIn("Execution API: eth_blockNumber", execution)


if __name__ == "__main__":
    unittest.main()
