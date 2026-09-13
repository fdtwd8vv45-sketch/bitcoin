from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agentic_wallet import (
    INSTALL_COMMAND,
    OVERVIEW_URL,
    _redact_status_payload,
    agentic_wallet_overview,
    agentic_wallet_status,
    run_wallet_status,
)
from bitcoin_tools import developer_howto
from local_cli import route_query

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERVIEW_DOC = REPO_ROOT / "BitcoinAgent" / "AGENTIC_WALLET.md"


class AgenticWalletOverviewTests(unittest.TestCase):
    def test_overview_covers_tee_login_and_x402(self) -> None:
        text = agentic_wallet_overview()
        lowered = text.lower()
        self.assertIn("tee", lowered)
        self.assertIn("email", lowered)
        self.assertIn("x402", lowered)
        self.assertIn(INSTALL_COMMAND, text)
        self.assertIn(OVERVIEW_URL, text)
        self.assertIn("does not send", lowered)

    def test_repo_overview_doc_exists(self) -> None:
        self.assertTrue(OVERVIEW_DOC.is_file())
        body = OVERVIEW_DOC.read_text(encoding="utf-8")
        self.assertIn("Trusted Execution", body)
        self.assertIn("Environment", body)
        self.assertIn(INSTALL_COMMAND, body)

    def test_howto_agentic_topic(self) -> None:
        text = developer_howto("agentic")
        self.assertIn(INSTALL_COMMAND, text)
        self.assertIn("tee", text.lower())
        self.assertEqual(developer_howto("agentic-wallet"), text)

    def test_local_cli_routes_overview_and_status(self) -> None:
        overview = route_query("what is agentic wallet")
        self.assertIn("TEE", overview)
        self.assertIn(INSTALL_COMMAND, overview)
        with patch("agentic_wallet.onchainos_cli_path", return_value=None):
            status = route_query("agentic wallet status")
        self.assertIn("not found", status.lower())
        self.assertIn(INSTALL_COMMAND, status)
        login = route_query("Log in to Agentic Wallet with email")
        self.assertIn(INSTALL_COMMAND, login)
        self.assertIn("email", login.lower())

    def test_local_cli_help_lists_agentic(self) -> None:
        text = route_query("help")
        self.assertIn("agentic", text)


class AgenticWalletStatusTests(unittest.TestCase):
    def test_status_without_cli(self) -> None:
        with patch("agentic_wallet.onchainos_cli_path", return_value=None):
            text = agentic_wallet_status()
        self.assertIn("not found", text.lower())
        self.assertIn(INSTALL_COMMAND, text)

    def test_status_logged_in(self) -> None:
        payload = {
            "ok": True,
            "data": {
                "loggedIn": True,
                "email": "user@example.com",
                "currentAccountId": "should-not-appear",
                "currentAccountName": "OKX Wallet - Main",
                "accountCount": 2,
                "accessToken": "leak",
                "policy": {"singleTxFlag": True},
            },
        }
        with patch("agentic_wallet.onchainos_cli_path", return_value="/usr/bin/onchainos"):
            with patch("agentic_wallet.run_wallet_status", return_value=payload):
                text = agentic_wallet_status()
        self.assertIn("Logged in: yes", text)
        self.assertIn("user@example.com", text)
        self.assertIn("OKX Wallet - Main", text)
        self.assertIn("Accounts: 2", text)
        self.assertNotIn("should-not-appear", text)
        self.assertNotIn("leak", text)

    def test_redact_drops_secret_fields(self) -> None:
        cleaned = _redact_status_payload(
            {"email": "a@b.c", "accessToken": "x", "currentAccountId": "uuid", "nested": {"apiKey": "k"}}
        )
        self.assertEqual(cleaned["email"], "a@b.c")
        self.assertNotIn("accessToken", cleaned)
        self.assertNotIn("currentAccountId", cleaned)
        self.assertEqual(cleaned["nested"], {})

    def test_run_wallet_status_uses_status_argv_only(self) -> None:
        class Result:
            returncode = 0
            stdout = json.dumps({"ok": True, "data": {"loggedIn": False, "accountCount": 0}}).encode()
            stderr = b""

        with patch("agentic_wallet.subprocess.run", return_value=Result()) as mocked:
            payload = run_wallet_status("/opt/onchainos")
        mocked.assert_called_once()
        args = mocked.call_args.args[0]
        self.assertEqual(args, ["/opt/onchainos", "wallet", "status"])
        self.assertFalse(payload.get("data", {}).get("loggedIn", True))


if __name__ == "__main__":
    unittest.main()
