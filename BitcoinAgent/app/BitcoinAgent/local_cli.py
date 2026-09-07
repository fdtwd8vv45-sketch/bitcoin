#!/usr/bin/env python3
"""Use BitcoinAgent tools without AWS, Bedrock, or AgentCore.

    python3 local_cli.py "What does getblockcount do?"
    python3 local_cli.py rpc sendtoaddress
    python3 local_cli.py          # interactive prompt
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable

from bitcoin_tools import developer_howto, list_rpc_methods, load_rpc_index, lookup_rpc, search_docs
from local_notes import recall_notes, remember_note
from network_tools import chain_tip_height, difficulty_adjustment, lookup_transaction, recommended_fees
from receive_check import check_receive, classify_payment_id

_TXID = re.compile(r"\b([0-9a-fA-F]{64})\b")
_HELP = """Commands (no AWS required):
  rpc <name>          Look up a JSON-RPC method
  list [category]     List RPC methods
  docs <query>        Search Bitcoin Core markdown docs
  howto <topic>       build | test | contribute | rpc | agent | local | receive | wallet
  wallet              How a payment arrives in a wallet
  fees                Recommended fees from mempool.space
  tip                 Current chain tip height
  difficulty          Difficulty-adjustment estimate
  tx <txid>           Public transaction lookup
  receive [addr|txid] Why a payment might not show up
  remember <text>     Save a short local note
  notes [query]       Show local notes
  help                This list
  quit                Exit the prompt

Or type a question: "What does getbalance do?" / "I didn't receive my bitcoin"
"""


def _rpc_names() -> set[str]:
    return {name.lower() for name in load_rpc_index()}


def _first_rpc_in(text: str) -> str | None:
    names = _rpc_names()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text):
        if token.lower() in names:
            return token
    return None


def _looks_like_receive(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(not receiving|wasn'?t receiving|isn'?t receiving|"
            r"didn'?t receive|did not receive|haven'?t received|"
            r"missing (payment|bitcoin|btc|crypto)|where is my|"
            r"didn'?t get my|waiting (on|for) (my )?(payment|bitcoin|btc)|"
            r"receiving my (crypto|bitcoin|btc))\b",
            lower,
        )
    )


def _looks_like_into_wallet(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(get (it|them|the (bitcoin|btc|crypto|coins?)) to|"
            r"into (the |my )?wallet|to the wallet|to my wallet|"
            r"show up in (the |my )?wallet|"
            r"how do (i|we) (get|receive|deposit))\b",
            lower,
        )
    )


def _receive_from_arg(text: str) -> str:
    address = ""
    txid = ""
    for token in re.findall(r"[A-Za-z0-9]+", text or ""):
        kind = classify_payment_id(token)
        if kind == "txid" and not txid:
            txid = token
        elif kind in {"bitcoin", "lightning", "ethereum", "testnet", "secret", "unknown"} and not address:
            if kind != "unknown":
                address = token
    if address and classify_payment_id(address) == "txid":
        return check_receive(txid=address)
    return check_receive(address=address, txid=txid)


def route_query(text: str) -> str:
    """Map a command or short question onto a tool. No model involved."""
    raw = text.strip()
    if not raw:
        return ""
    parts = raw.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    commands: dict[str, Callable[[], str]] = {
        "rpc": lambda: lookup_rpc(arg or "getblockcount"),
        "lookup": lambda: lookup_rpc(arg or "getblockcount"),
        "list": lambda: list_rpc_methods(arg),
        "docs": lambda: search_docs(arg or "JSON-RPC"),
        "search": lambda: search_docs(arg or "JSON-RPC"),
        "howto": lambda: developer_howto(arg or "local"),
        "wallet": lambda: developer_howto("wallet"),
        "fees": recommended_fees,
        "tip": chain_tip_height,
        "height": chain_tip_height,
        "difficulty": difficulty_adjustment,
        "tx": lambda: lookup_transaction(arg),
        "receive": lambda: _receive_from_arg(arg),
        "remember": lambda: remember_note(arg),
        "notes": lambda: recall_notes(arg),
        "recall": lambda: recall_notes(arg),
        "help": lambda: _HELP.strip(),
        "?": lambda: _HELP.strip(),
    }
    if cmd in commands:
        return commands[cmd]()

    lower = raw.lower()
    txid = _TXID.search(raw)
    if _looks_like_into_wallet(lower) and not _TXID.search(raw):
        return developer_howto("receive")
    if _looks_like_receive(lower):
        return _receive_from_arg(raw)
    if txid and ("tx" in lower or "transaction" in lower or "txid" in lower):
        return lookup_transaction(txid.group(1))
    if lower in {"fees", "fee", "feerate", "recommended fees"} or "recommended fee" in lower:
        return recommended_fees()
    if "difficulty" in lower:
        return difficulty_adjustment()
    if re.search(r"\b(tip|block height|chain height)\b", lower) and not _first_rpc_in(raw):
        return chain_tip_height()
    if lower.startswith("remember "):
        return remember_note(raw[9:])

    rpc_name = _first_rpc_in(raw)
    if rpc_name and re.search(r"\b(rpc|what does|explain|lookup|method)\b", lower):
        return lookup_rpc(rpc_name)
    if rpc_name and len(raw.split()) <= 2:
        return lookup_rpc(rpc_name)

    howto_topics = {
        "build": "build",
        "compile": "build",
        "cmake": "build",
        "test": "test",
        "functional": "test",
        "contribute": "contribute",
        "contributing": "contribute",
        "json-rpc": "rpc",
        "bitcoin-cli": "rpc",
        "agent": "agent",
        "local": "local",
        "receive": "receive",
        "wallet": "wallet",
    }
    for needle, topic in howto_topics.items():
        if needle in lower and re.search(r"\b(how|build|run|test|contribute|start)\b", lower):
            return developer_howto(topic)

    if rpc_name:
        return lookup_rpc(rpc_name)
    return search_docs(raw)


def repl() -> None:
    print("BitcoinAgent local tools. Type help, or a question. No AWS needed.")
    while True:
        try:
            line = input("btc> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line.lower() in {"quit", "exit"}:
            return
        print(route_query(line))
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Call BitcoinAgent tools locally without AWS or Bedrock.",
    )
    parser.add_argument("query", nargs="*", help="Command or question. Omit for an interactive prompt.")
    args = parser.parse_args()
    if not args.query:
        if sys.stdin.isatty():
            repl()
            return
        raw = sys.stdin.read()
        if not raw.strip():
            print(_HELP)
            return
        print(route_query(raw))
        return
    print(route_query(" ".join(args.query)))


if __name__ == "__main__":
    main()
