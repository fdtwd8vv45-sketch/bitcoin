from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from network_tools import _get_json, lookup_transaction, recommended_fees
from payload import PayloadError, extract_prompt, validate_actor_id


class PayloadTests(unittest.TestCase):
    def test_prompt_required(self) -> None:
        with self.assertRaises(PayloadError):
            extract_prompt({})
        with self.assertRaises(PayloadError):
            extract_prompt({"prompt": 12})

    def test_prompt_too_long(self) -> None:
        with self.assertRaises(PayloadError):
            extract_prompt({"prompt": "x" * 10001})

    def test_prompt_sanitized(self) -> None:
        self.assertEqual(extract_prompt({"prompt": "  getblockcount \n\n please "}), "getblockcount please")

    def test_actor_id(self) -> None:
        self.assertEqual(validate_actor_id("alice"), "alice")
        with self.assertRaises(PayloadError):
            validate_actor_id("bad user!")


class NetworkToolTests(unittest.TestCase):
    def test_rejects_bad_txid(self) -> None:
        self.assertIn("64-character", lookup_transaction("not-a-txid"))

    def test_allowlist_blocks_other_hosts(self) -> None:
        with self.assertRaises(ValueError):
            _get_json("https://example.com/api")

    def test_recommended_fees_parses_json(self) -> None:
        payload = json.dumps({"fastestFee": 8, "hourFee": 2}).encode()

        class FakeResponse:
            def read(self, _n: int) -> bytes:
                return payload

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        with patch("network_tools.urllib.request.urlopen", return_value=FakeResponse()):
            text = recommended_fees()
        self.assertIn("fastestFee", text)
        self.assertIn("8", text)


if __name__ == "__main__":
    unittest.main()
