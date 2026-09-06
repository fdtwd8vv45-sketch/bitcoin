"""Help a user tell a receive delay from a real mistake.

Public explorer data only. Never ask for seed phrases, private keys, or
wallet passwords.
"""

from __future__ import annotations

import re
from typing import Any

from network_tools import _HEX64, _get_json
from optional_tool import tool

# Mainnet Bitcoin addresses only. Other strings are classified so we can
# explain the usual mix-ups (Lightning invoice, Ethereum, testnet).
_P2PKH = re.compile(r"^1[1-9A-HJ-NP-Za-km-z]{24,33}$")
_P2SH = re.compile(r"^3[1-9A-HJ-NP-Za-km-z]{24,33}$")
_BECH32 = re.compile(r"^bc1[qp][ac-hj-np-z02-9]{8,87}$")
_ETH = re.compile(r"^0x[0-9a-fA-F]{40}$")
_WIF = re.compile(r"^[5KL][1-9A-HJ-NP-Za-km-z]{50,51}$")

CHECKLIST = """Not receiving bitcoin is usually one of these — not "you broke it":

1. It is still unconfirmed. Low-fee payments can sit in the mempool for hours.
   Exchanges often wait for 2–6 confirmations before they credit you.
2. You are looking in the wrong wallet or a different app than the one that
   created the address.
3. The sender used a different network. Bitcoin on-chain, Lightning, and
   "BTC" on an exchange that actually ships another coin are not the same.
4. The address was copied wrong, or it is a testnet / Lightning / Ethereum
   address. Those will never show up in a Bitcoin mainnet wallet.
5. The sender has not actually broadcast the transaction yet.

What to paste here (these are public; they are not secrets):
- the receive address, or
- the 64-character transaction id (txid) from the sender

Never paste a seed phrase, private key, or wallet password.

Commands:
  receive
  receive <address>
  receive <txid>
"""


def classify_payment_id(value: str) -> str:
    text = value.strip()
    if not text:
        return "empty"
    if _WIF.match(text) or text.lower().startswith(("xprv", "xpub")):
        return "secret"
    if text.lower().startswith(("lnbc", "lntb", "lnbcrt")):
        return "lightning"
    if _ETH.match(text):
        return "ethereum"
    if text.lower().startswith(("tb1", "bcrt1")):
        return "testnet"
    if _HEX64.match(text):
        return "txid"
    lowered = text.lower()
    if _P2PKH.match(text) or _P2SH.match(text) or _BECH32.match(lowered):
        return "bitcoin"
    return "unknown"


def _sats_to_btc(sats: Any) -> str:
    try:
        value = int(sats)
    except (TypeError, ValueError):
        return "unknown"
    return f"{value / 100_000_000:.8f}".rstrip("0").rstrip(".") + " BTC"


def _error(payload: Any) -> str | None:
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    return None


def _address_report(address: str) -> str:
    data = _get_json(f"https://mempool.space/api/address/{address}")
    err = _error(data)
    if err:
        return (
            f"Address {address} was not found as a Bitcoin mainnet address ({err}).\n"
            "Check for a typo, or that it is not testnet / Lightning / another coin."
        )
    chain = data.get("chain_stats") or {}
    mempool = data.get("mempool_stats") or {}
    confirmed = int(chain.get("funded_txo_sum") or 0)
    pending = int(mempool.get("funded_txo_sum") or 0)
    confirmed_count = int(chain.get("tx_count") or 0)
    pending_count = int(mempool.get("tx_count") or 0)
    lines = [
        f"Address: {address}",
        f"Confirmed received: {_sats_to_btc(confirmed)} across {confirmed_count} transaction(s)",
        f"Unconfirmed (mempool): {_sats_to_btc(pending)} across {pending_count} transaction(s)",
    ]
    if confirmed == 0 and pending == 0:
        lines.append(
            "Nothing has reached this address yet. Either the sender has not "
            "broadcast the payment, they used a different address, or it is "
            "still too new to appear. Ask them for the txid."
        )
    elif pending and not confirmed:
        lines.append(
            "A payment is in the mempool but not confirmed. That is usually a "
            "wait, not a mistake. Watch confirmations; do not send a second "
            "payment unless the sender says the first one failed."
        )
    else:
        lines.append("This address has received bitcoin on mainnet. If your wallet is still empty, you are likely looking at a different wallet than the one that owns this address.")
    return "\n".join(lines)


def _tx_report(txid: str, expected_address: str = "") -> str:
    data = _get_json(f"https://mempool.space/api/tx/{txid}")
    err = _error(data)
    if err:
        return (
            f"Transaction {txid} was not found ({err}). "
            "The sender may not have broadcast it, or the id was copied wrong."
        )
    status = data.get("status") or {}
    confirmed = bool(status.get("confirmed"))
    height = status.get("block_height")
    outputs = []
    for item in data.get("vout") or []:
        addr = item.get("scriptpubkey_address") or "(no address)"
        outputs.append(f"- {addr}: {_sats_to_btc(item.get('value'))}")
    lines = [
        f"Transaction: {txid}",
        f"Status: {'confirmed' if confirmed else 'unconfirmed (in the mempool)'}",
    ]
    if confirmed and height is not None:
        tip = _get_json("https://mempool.space/api/blocks/tip/height")
        if isinstance(tip, int):
            confs = tip - int(height) + 1
            lines.append(f"Confirmations: {confs} (included in block {height})")
            if confs < 6:
                lines.append("Some wallets and almost all exchanges wait for several confirmations before they show the money as available.")
        else:
            lines.append(f"Included in block {height}")
    elif not confirmed:
        fee = data.get("fee")
        if fee is not None:
            lines.append(f"Fee: {fee} sat")
        lines.append("Unconfirmed usually means wait. A second send can make things worse.")
    if outputs:
        lines.append("Pays:")
        lines.extend(outputs)
    if expected_address:
        paid = any(
            (item.get("scriptpubkey_address") or "") == expected_address
            for item in (data.get("vout") or [])
        )
        if paid:
            lines.append(f"This transaction does pay {expected_address}.")
        else:
            lines.append(
                f"This transaction does not pay {expected_address}. "
                "The sender used a different address, or this is the wrong txid."
            )
    return "\n".join(lines)


@tool
def check_receive(address: str = "", txid: str = "") -> str:
    """Explain why incoming bitcoin might not show up, and look up a public address or txid.

    Use when the user thinks they did not receive crypto or worries they made
    a mistake. Pass a Bitcoin mainnet address and/or a 64-character txid.
    Never ask for seed phrases or private keys.
    """
    address = address.strip()
    txid = txid.strip()
    parts: list[str] = []

    if address:
        kind = classify_payment_id(address)
        if kind == "secret":
            return "That looks like a secret key. Do not paste it. Use a receive address or a txid instead."
        if kind == "lightning":
            return (
                "That is a Lightning invoice, not a Bitcoin on-chain address. "
                "It will not appear in a normal Bitcoin address history. "
                "Check the Lightning wallet that created the invoice."
            )
        if kind == "ethereum":
            return (
                "That is an Ethereum address (starts with 0x). Bitcoin cannot "
                "be received there. If someone sent BTC to it, the coins are "
                "not in a Bitcoin wallet."
            )
        if kind == "testnet":
            return (
                "That looks like Bitcoin testnet or regtest. Mainnet wallets "
                "will never show those coins."
            )
        if kind == "txid" and not txid:
            txid = address
            address = ""
        elif kind != "bitcoin":
            return (
                f"Could not recognize {address!r} as a Bitcoin mainnet address "
                "or txid. Paste the address from your wallet's receive screen, "
                "or the 64-character txid from the sender."
            )
        else:
            parts.append(_address_report(address))

    if txid:
        kind = classify_payment_id(txid)
        if kind == "secret":
            return "That looks like a secret key. Do not paste it."
        if kind != "txid":
            return "txid must be a 64-character hexadecimal transaction id."
        parts.append(_tx_report(txid, expected_address=address))

    if not parts:
        return CHECKLIST
    return "\n\n".join(parts)
