from __future__ import annotations

import unittest

from bitcoin_tools import (
    build_rpc_index,
    developer_howto,
    list_rpc_methods,
    load_rpc_index,
    lookup_rpc,
    repo_root,
    search_docs,
)
from payload import strip_trailing_tool_use


class BitcoinToolsTests(unittest.TestCase):
    def test_repo_root_points_at_bitcoin_core(self) -> None:
        root = repo_root()
        self.assertIsNotNone(root)
        assert root is not None
        self.assertTrue((root / "src" / "rpc" / "blockchain.cpp").is_file())

    def test_build_rpc_index_includes_getblockcount(self) -> None:
        index = build_rpc_index()
        self.assertIn("getblockcount", index)
        entry = index["getblockcount"]
        self.assertEqual(entry["category"], "blockchain")
        self.assertIn("height", entry["description"].lower())
        self.assertTrue(entry["source"].endswith("blockchain.cpp"))

    def test_build_rpc_index_includes_wallet_methods(self) -> None:
        index = build_rpc_index()
        self.assertIn("getbalance", index)
        self.assertIn("sendtoaddress", index)
        self.assertIn("bumpfee", index)
        self.assertEqual(index["getbalance"]["category"], "wallet")
        self.assertEqual(index["sendtoaddress"]["category"], "wallet")
        self.assertIn("available balance", index["getbalance"]["description"].lower())
        self.assertIn("send an amount", index["sendtoaddress"]["description"].lower())
        self.assertIn("bumps the fee", index["bumpfee"]["description"].lower())

    def test_lookup_rpc_exact_and_unknown(self) -> None:
        text = lookup_rpc("getblockcount")
        self.assertIn("RPC: getblockcount", text)
        self.assertIn("blockchain", text)
        self.assertIn("No RPC method matching", lookup_rpc("notarealrpc"))

    def test_list_rpc_methods_filters_category(self) -> None:
        load_rpc_index.cache_clear()
        text = list_rpc_methods("blockchain")
        self.assertIn("getblockcount", text)

    def test_search_docs_finds_json_rpc(self) -> None:
        text = search_docs("JSON-RPC endpoints")
        self.assertIn("JSON-RPC", text)
        self.assertIn("doc/", text)

    def test_developer_howto_topics(self) -> None:
        self.assertIn("cmake", developer_howto("build").lower())
        self.assertIn("ctest", developer_howto("test").lower())
        self.assertIn("Receive", developer_howto("receive"))
        self.assertIn("getnewaddress", developer_howto("wallet"))
        self.assertIn("Unknown topic", developer_howto("spaceships"))

    def test_strip_trailing_tool_use(self) -> None:
        messages = [
            {"role": "user", "content": [{"text": "hi"}]},
            {"role": "assistant", "content": [{"toolUse": {"name": "lookup_rpc"}}]},
        ]
        cleaned = strip_trailing_tool_use(messages)
        self.assertEqual(cleaned, [{"role": "user", "content": [{"text": "hi"}]}])


if __name__ == "__main__":
    unittest.main()
