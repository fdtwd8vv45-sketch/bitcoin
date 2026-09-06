from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from local_cli import route_query
from receive_check import check_receive, classify_payment_id


class ClassifyTests(unittest.TestCase):
    def test_kinds(self) -> None:
        self.assertEqual(classify_payment_id("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"), "bitcoin")
        self.assertEqual(classify_payment_id("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"), "bitcoin")
        self.assertEqual(classify_payment_id("tb1qexampleaddresstestnet000000000000000"), "testnet")
        self.assertEqual(classify_payment_id("0x0000000000000000000000000000000000000000"), "ethereum")
        self.assertEqual(classify_payment_id("lnbc20m1pvjluez"), "lightning")
        self.assertEqual(classify_payment_id("a" * 64), "txid")
        self.assertEqual(classify_payment_id("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ"), "secret")


class ReceiveCheckTests(unittest.TestCase):
    def test_checklist_without_ids(self) -> None:
        text = check_receive()
        self.assertIn("still unconfirmed", text)
        self.assertIn("Never paste a seed phrase", text)

    def test_rejects_secret(self) -> None:
        text = check_receive(address="5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ")
        self.assertIn("secret", text.lower())

    def test_explains_ethereum(self) -> None:
        text = check_receive(address="0x0000000000000000000000000000000000000000")
        self.assertIn("Ethereum", text)

    def test_explains_lightning(self) -> None:
        text = check_receive(address="lnbc20m1pvjluezpp")
        self.assertIn("Lightning", text)

    def test_address_empty_vs_funded(self) -> None:
        empty = {
            "chain_stats": {"funded_txo_sum": 0, "tx_count": 0},
            "mempool_stats": {"funded_txo_sum": 0, "tx_count": 0},
        }
        with patch("receive_check._get_json", return_value=empty):
            text = check_receive(address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        self.assertIn("Nothing has reached this address yet", text)

        pending = {
            "chain_stats": {"funded_txo_sum": 0, "tx_count": 0},
            "mempool_stats": {"funded_txo_sum": 50_000, "tx_count": 1},
        }
        with patch("receive_check._get_json", return_value=pending):
            text = check_receive(address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        self.assertIn("mempool", text.lower())
        self.assertIn("0.0005 BTC", text)

    def test_txid_pays_expected_address(self) -> None:
        tx = {
            "status": {"confirmed": True, "block_height": 100},
            "vout": [{"scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "value": 100000000}],
            "fee": 200,
        }

        def fake_get(url: str):
            if url.endswith("/tx/" + "ab" * 32):
                return tx
            if url.endswith("/blocks/tip/height"):
                return 105
            return {"error": "unexpected " + url}

        with patch("receive_check._get_json", side_effect=fake_get):
            text = check_receive(address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", txid="ab" * 32)
        self.assertIn("Confirmations: 6", text)
        self.assertIn("does pay 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", text)
        self.assertIn("1 BTC", text)


class ReceiveRoutingTests(unittest.TestCase):
    def test_plain_question(self) -> None:
        text = route_query("I didn't receive my crypto")
        self.assertIn("still unconfirmed", text)
        text = route_query(
            "I just didn't know if I wasn't receiving my crypto because I was making mistakes"
        )
        self.assertIn("still unconfirmed", text)

    def test_receive_command(self) -> None:
        text = route_query("receive")
        self.assertIn("Never paste a seed phrase", text)

    def test_howto_receive(self) -> None:
        text = route_query("howto receive")
        self.assertIn("txid", text.lower())


class LookupAddressTests(unittest.TestCase):
    def test_lookup_address_parses(self) -> None:
        from network_tools import lookup_address

        payload = json.dumps({"address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}).encode()

        class FakeResponse:
            def read(self, _n: int) -> bytes:
                return payload

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        with patch("network_tools.urllib.request.urlopen", return_value=FakeResponse()):
            text = lookup_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        self.assertIn("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", text)


if __name__ == "__main__":
    unittest.main()
