from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from contract_source import (
    DOCS_URL,
    abi_summary,
    etherscan_get,
    format_contract_result,
    lookup_contract_source,
    normalize_chain_id,
    parse_source_files,
)
from local_cli import route_query

USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
EXAMPLE = "0xBB9bc244D798123fDe783fCc1C72d3Bb8C189413"

_SINGLE_SOURCE = (
    "pragma solidity 0.4.26;\r\n\r\ncontract Test12345 {\r\n"
    "    string public test;\r\n}\r\n"
)
_SINGLE_ABI = json.dumps(
    [
        {
            "constant": False,
            "inputs": [{"name": "_c", "type": "string"}],
            "name": "enterValue",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "test",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
    ]
)
_VERIFIED = {
    "SourceCode": _SINGLE_SOURCE,
    "ABI": _SINGLE_ABI,
    "ContractName": "Test12345",
    "CompilerVersion": "v0.4.26+commit.4563c3fc",
    "CompilerType": "solc",
    "OptimizationUsed": "1",
    "Runs": "200",
    "ConstructorArguments": "",
    "EVMVersion": "Default",
    "Library": "",
    "ContractFileName": "",
    "LicenseType": "None",
    "Proxy": "0",
    "Implementation": "",
    "SwarmSource": "bzzr://abc",
    "SimilarMatch": "0x60810f4d8a618edb533a168e790ab6c09b0e7707",
}


def _ok(entry: dict) -> dict:
    return {"status": "1", "message": "OK", "result": [entry]}


def _fake_response(payload: dict | str):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    class FakeResponse:
        def read(self, _n: int) -> bytes:
            return raw

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    return FakeResponse()


class NormalizeChainTests(unittest.TestCase):
    def test_aliases_and_digits(self) -> None:
        self.assertEqual(normalize_chain_id(None), "1")
        self.assertEqual(normalize_chain_id(""), "1")
        self.assertEqual(normalize_chain_id("ethereum"), "1")
        self.assertEqual(normalize_chain_id("arbitrum"), "42161")
        self.assertEqual(normalize_chain_id("42161"), "42161")
        self.assertEqual(normalize_chain_id("chainid=10"), "10")
        self.assertIsNone(normalize_chain_id("not-a-chain"))
        self.assertIsNone(normalize_chain_id("1;drop"))


class ParseSourceTests(unittest.TestCase):
    def test_single_file(self) -> None:
        files = parse_source_files("pragma solidity ^0.8.0;\ncontract A {}")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0][0], "source.sol")
        self.assertIn("contract A", files[0][1])

    def test_standard_json_wrapped(self) -> None:
        inner = {
            "language": "Solidity",
            "sources": {
                "contracts/Vault.sol": {"content": "contract Vault {}"},
                "contracts/Lib.sol": {"content": "library Lib {}"},
            },
            "settings": {"optimizer": {"enabled": True}},
        }
        wrapped = "{" + json.dumps(inner) + "}"
        files = parse_source_files(wrapped)
        names = [name for name, _content in files]
        self.assertEqual(names, ["contracts/Vault.sol", "contracts/Lib.sol"])
        self.assertIn("Vault", files[0][1])

    def test_empty(self) -> None:
        self.assertEqual(parse_source_files(""), [])
        self.assertEqual(parse_source_files("   "), [])


class AbiSummaryTests(unittest.TestCase):
    def test_function_list(self) -> None:
        text = abi_summary(_SINGLE_ABI)
        self.assertIn("function enterValue (nonpayable)", text)
        self.assertIn("function test (view)", text)

    def test_unverified_passthrough(self) -> None:
        self.assertEqual(
            abi_summary("Contract source code not verified"),
            "Contract source code not verified",
        )


class LookupContractSourceTests(unittest.TestCase):
    def test_missing_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ETHERSCAN_API_KEY", None)
            text = lookup_contract_source(EXAMPLE)
        self.assertIn("ETHERSCAN_API_KEY", text)
        self.assertIn("etherscan.io/apidashboard", text)
        self.assertNotIn("apikey=", text.lower())

    def test_rejects_bad_address(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "test-key"}):
            self.assertIn("20-byte", lookup_contract_source("not-an-address"))
            self.assertIn("Do not paste", lookup_contract_source("my private key 0x00"))

    def test_rejects_bad_chain(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "test-key"}):
            self.assertIn("chainid must be", lookup_contract_source(EXAMPLE, "nope"))

    def test_allowlist_blocks_other_hosts(self) -> None:
        from contract_source import _get_json

        with self.assertRaises(ValueError):
            _get_json("https://example.com/v2/api")

    def test_verified_single_file(self) -> None:
        captured: dict[str, str] = {}

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            return _fake_response(_ok(_VERIFIED))

        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "test-key"}):
            with patch("contract_source.urllib.request.urlopen", side_effect=fake_urlopen):
                text = lookup_contract_source(EXAMPLE, "ethereum")
        self.assertIn("module=contract", captured["url"])
        self.assertIn("action=getsourcecode", captured["url"])
        self.assertIn("chainid=1", captured["url"])
        self.assertIn("apikey=test-key", captured["url"])
        self.assertIn("Contract: Test12345", text)
        self.assertIn("Verified: yes", text)
        self.assertIn("solc v0.4.26+commit.4563c3fc", text)
        self.assertIn("pragma solidity 0.4.26", text)
        self.assertIn("function enterValue", text)
        self.assertIn("Similar verified match", text)
        self.assertIn(DOCS_URL, text)
        self.assertNotIn("test-key", text)
        self.assertNotIn("apikey=", text)

    def test_unverified(self) -> None:
        entry = {
            "SourceCode": "",
            "ABI": "Contract source code not verified",
            "ContractName": "",
            "CompilerVersion": "",
        }
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "test-key"}):
            with patch(
                "contract_source.urllib.request.urlopen",
                return_value=_fake_response(_ok(entry)),
            ):
                text = lookup_contract_source(USDT)
        self.assertIn("Verified: no", text)
        self.assertIn("not verified", text.lower())
        self.assertNotIn("pragma", text)

    def test_proxy_points_at_implementation(self) -> None:
        entry = dict(_VERIFIED)
        entry["Proxy"] = "1"
        entry["Implementation"] = "0x1111111111111111111111111111111111111111"
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "test-key"}):
            with patch(
                "contract_source.urllib.request.urlopen",
                return_value=_fake_response(_ok(entry)),
            ):
                text = lookup_contract_source(EXAMPLE)
        self.assertIn("Proxy: 1", text)
        self.assertIn("0x1111111111111111111111111111111111111111", text)
        self.assertIn("call this tool again on the implementation", text)

    def test_api_status_zero(self) -> None:
        payload = {"status": "0", "message": "NOTOK", "result": "Invalid API Key"}
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "test-key"}):
            with patch(
                "contract_source.urllib.request.urlopen",
                return_value=_fake_response(payload),
            ):
                text = lookup_contract_source(EXAMPLE)
        self.assertEqual(text, "Invalid API Key")
        self.assertNotIn("test-key", text)

    def test_etherscan_get_requires_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ETHERSCAN_API_KEY", None)
            payload = etherscan_get({"module": "contract", "action": "getsourcecode"})
        self.assertIn("ETHERSCAN_API_KEY", payload["error"])


class FormatResultTests(unittest.TestCase):
    def test_picks_main_file_from_standard_json(self) -> None:
        inner = {
            "language": "Solidity",
            "sources": {
                "contracts/Lib.sol": {"content": "library Lib {}"},
                "contracts/Vault.sol": {"content": "contract Vault { function deposit() {} }"},
            },
        }
        entry = dict(_VERIFIED)
        entry["SourceCode"] = json.dumps(inner)
        entry["ContractName"] = "Vault"
        entry["ContractFileName"] = "contracts/Vault.sol"
        text = format_contract_result(EXAMPLE, "1", entry)
        self.assertIn("Source files (2)", text)
        self.assertIn("## contracts/Vault.sol", text)
        self.assertIn("function deposit", text)
        self.assertIn("Other files not printed: contracts/Lib.sol", text)


class LocalCliContractSourceTests(unittest.TestCase):
    def test_help_lists_source(self) -> None:
        text = route_query("help")
        self.assertIn("source <0xaddr>", text)

    def test_source_command_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ETHERSCAN_API_KEY", None)
            text = route_query(f"source {EXAMPLE}")
        self.assertIn("ETHERSCAN_API_KEY", text)

    def test_natural_language_routes_to_source(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "test-key"}):
            with patch(
                "contract_source.urllib.request.urlopen",
                return_value=_fake_response(_ok(_VERIFIED)),
            ):
                text = route_query(f"get verified source code for {USDT} on ethereum")
        self.assertIn("Contract: Test12345", text)
        self.assertIn("Verified: yes", text)

    def test_source_command_with_chain(self) -> None:
        captured: dict[str, str] = {}

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            return _fake_response(_ok(_VERIFIED))

        with patch.dict(os.environ, {"ETHERSCAN_API_KEY": "test-key"}):
            with patch("contract_source.urllib.request.urlopen", side_effect=fake_urlopen):
                text = route_query(f"source {EXAMPLE} arbitrum")
        self.assertIn("chainid=42161", captured["url"])
        self.assertIn("Chain ID: 42161", text)

    def test_receive_still_explains_ethereum(self) -> None:
        text = route_query(f"receive {EXAMPLE}")
        self.assertIn("Ethereum", text)
        self.assertNotIn("ETHERSCAN_API_KEY", text)


if __name__ == "__main__":
    unittest.main()
