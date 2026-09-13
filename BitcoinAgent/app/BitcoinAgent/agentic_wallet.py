"""OKX Agentic Wallet overview and read-only CLI status.

Key generation, storage, and signing stay in OKX's TEE. This module never
sends, swaps, signs, logs in, or stores OTP / API credentials.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from optional_tool import tool

OVERVIEW_URL = "https://web3.okx.com/onchainos/dev-docs/wallet/agentic-wallet"
INSTALL_URL = "https://web3.okx.com/onchainos/dev-docs/wallet/install-your-agentic-wallet"
PAYMENTS_URL = "https://web3.okx.com/onchainos/dev-docs/payments/payment-use-buyer"
SKILLS_URL = "https://github.com/okx/onchainos-skills"
INSTALL_COMMAND = "npx -y @okxweb3/onchainos-installer install"
_STATUS_TIMEOUT_SECONDS = 8
_MAX_STATUS_BYTES = 32_000
_SECRET_FIELD_NAMES = {
    "accesstoken",
    "refreshtoken",
    "apikey",
    "secretkey",
    "passphrase",
    "sessionkey",
    "sessioncert",
    "teeid",
    "sateeid",
    "encryptedsessionsk",
    "signingkey",
    "currentaccountid",
    "accountid",
}


def _overview_text() -> str:
    return (
        "Agentic Wallet (OKX) is an agent-native onchain wallet. Key generation, "
        "storage, and signing happen inside a TEE. This process never sees the "
        "private key.\n"
        "\n"
        "Why an agent needs one:\n"
        "- Closed-loop execution — signal to onchain settlement without pasting keys.\n"
        "- 24/7 availability — the official CLI can stay signed in; this agent still "
        "will not place trades.\n"
        "- Risk checks — malicious approvals and unusual transfers can be flagged "
        "before TEE signing.\n"
        "- Up to 50 sub-wallets for isolated positions.\n"
        "- Autonomous payments on the x402 protocol when an API returns HTTP 402.\n"
        "\n"
        "What the official OKX CLI / skills can do:\n"
        "- Automated strategy execution (not wrapped by BitcoinAgent).\n"
        "- Multi-chain balances, risk detection, approval review.\n"
        "- Batch transfers and parallel accounts.\n"
        "- x402 auto-pay for paid APIs.\n"
        "- Market / smart-money monitoring (separate OKX skills).\n"
        "- Sign-in with email, Google, or Apple. No seed phrase in this chat.\n"
        "\n"
        "Install (Node.js 18+):\n"
        f"  {INSTALL_COMMAND}\n"
        "Then tell an agent that has the Onchain OS skills:\n"
        '  Log in to Agentic Wallet with email\n'
        "(or Google / Apple). Open the returned URL, finish OTP or OAuth. The "
        "first login creates EVM and Solana addresses; the same email restores "
        "the wallet.\n"
        "\n"
        "This BitcoinAgent tool is overview + status only. It does not send, "
        "swap, trade, or sign. That stays in the official onchainos CLI.\n"
        "\n"
        "Not a Bitcoin Core wallet. Coins sent to bitcoin-cli getnewaddress do "
        "not appear here, and Agentic Wallet addresses are not bitcoind wallets.\n"
        "\n"
        f"Docs: {OVERVIEW_URL}\n"
        f"Install: {INSTALL_URL}\n"
        f"x402 payments: {PAYMENTS_URL}\n"
        f"CLI / skills: {SKILLS_URL}\n"
        "Local: python3 BitcoinAgent/app/BitcoinAgent/local_cli.py agentic status"
    )


def _redact_status_payload(value: Any) -> Any:
    """Drop credential-like keys before anything is shown to the model."""
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).replace("_", "").lower() in _SECRET_FIELD_NAMES:
                continue
            cleaned[str(key)] = _redact_status_payload(item)
        return cleaned
    if isinstance(value, list):
        return [_redact_status_payload(item) for item in value]
    return value


def _format_status_payload(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    if not isinstance(data, dict):
        data = payload if any(key in payload for key in ("loggedIn", "email", "accountCount")) else {}
    logged_in = data.get("loggedIn")
    email = data.get("email") or ""
    name = data.get("currentAccountName") or ""
    count = data.get("accountCount")
    lines = [
        "onchainos CLI: found",
        f"Logged in: {'yes' if logged_in else 'no'}",
    ]
    if email:
        lines.append(f"Email: {email}")
    if name:
        lines.append(f"Active account: {name}")
    if isinstance(count, (int, float)):
        lines.append(f"Accounts: {int(count)} (OKX allows up to 50)")
    policy = data.get("policy")
    if isinstance(policy, dict) and policy:
        lines.append("Spending policy is configured on this account (limits are set in the OKX portal).")
    if not logged_in:
        lines.append(
            "Not signed in. Ask an Onchain OS agent: "
            '"Log in to Agentic Wallet with email" (or Google / Apple).'
        )
    lines.append("BitcoinAgent will not send, swap, or sign. Use the official onchainos CLI for that.")
    return "\n".join(lines)


def onchainos_cli_path() -> str | None:
    return shutil.which("onchainos")


def run_wallet_status(cli_path: str | None = None) -> dict[str, Any]:
    """Run `onchainos wallet status` only. Never login / send / sign."""
    binary = cli_path or onchainos_cli_path()
    if not binary:
        return {"error": "onchainos CLI is not on PATH"}
    try:
        completed = subprocess.run(
            [binary, "wallet", "status"],
            check=False,
            capture_output=True,
            timeout=_STATUS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"error": "onchainos wallet status timed out"}
    except OSError:
        return {"error": "Could not execute onchainos"}
    raw = completed.stdout or completed.stderr
    if len(raw) > _MAX_STATUS_BYTES:
        return {"error": "onchainos wallet status returned too much data"}
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": "onchainos wallet status returned a non-text body"}
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        snippet = decoded.strip().splitlines()[0][:160] if decoded.strip() else "empty output"
        if completed.returncode != 0:
            return {"error": f"onchainos wallet status failed: {snippet}"}
        return {"error": f"onchainos wallet status returned non-JSON: {snippet}"}
    if not isinstance(parsed, dict):
        return {"error": "onchainos wallet status returned a non-object"}
    return _redact_status_payload(parsed)


@tool
def agentic_wallet_overview() -> str:
    """Explain OKX Agentic Wallet: TEE keys, email login, x402, and what this agent will not do."""
    return _overview_text()


@tool
def agentic_wallet_status() -> str:
    """Check whether the official onchainos CLI is installed and logged in.

    Read-only. Does not login, send, swap, or sign.
    """
    binary = onchainos_cli_path()
    if not binary:
        return (
            "onchainos CLI: not found on PATH.\n"
            f"Install: {INSTALL_COMMAND}\n"
            f"Then: {INSTALL_URL}\n"
            "After install, sign in with email, Google, or Apple via the official "
            "Onchain OS skills — not through BitcoinAgent."
        )
    payload = _redact_status_payload(run_wallet_status(binary))
    if isinstance(payload, dict) and payload.get("error") and set(payload) <= {"error"}:
        return (
            f"onchainos CLI: {binary}\n"
            f"{payload['error']}\n"
            "Status is read-only. BitcoinAgent will not run login, send, or sign."
        )
    if not isinstance(payload, dict):
        return "onchainos wallet status returned an unexpected payload."
    return _format_status_payload(payload)
