#!/usr/bin/env python3
"""Use BitcoinAgent tools without AWS, Bedrock, or AgentCore.

    python3 local_cli.py "What does getblockcount do?"
    python3 local_cli.py rpc sendtoaddress
    python3 local_cli.py source 0xdAC17F958D2ee523a2206206994597C13D831ec7
    python3 local_cli.py agentic
    python3 local_cli.py jupiter price SOL,JUP
    python3 local_cli.py phantom
    python3 local_cli.py phantom packages
    python3 local_cli.py coinstats coin bitcoin
    python3 local_cli.py libbndl inspect path/to/file.BNDL
    python3 local_cli.py libbndl extract path/to/file.BNDL hello.txt
    python3 local_cli.py apko plan path/to/images.apko.json
    python3 local_cli.py execution
    python3 local_cli.py execution eth_blockNumber
    python3 local_cli.py etherscan-stats
    python3 local_cli.py etherscan-stats snapshot
    python3 local_cli.py          # interactive prompt
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable

from agentic_wallet import agentic_wallet_overview, agentic_wallet_status
from apko_smoke import apko_from_arg, apko_smoke_overview
from bitcoin_tools import developer_howto, list_rpc_methods, load_rpc_index, lookup_rpc, search_docs
from contract_source import lookup_contract_source, normalize_chain_id
from jupiter import (
    jupiter_cli_status,
    jupiter_overview,
    jupiter_price,
    jupiter_token_search,
    jupiter_verify_eligibility,
)
from phantom_connect import (
    phantom_connect_cli_status,
    phantom_connect_overview,
    phantom_connect_packages,
)
from coinstats import (
    coinstats_coin,
    coinstats_markets,
    coinstats_overview,
    coinstats_portfolio,
    coinstats_portfolio_list,
    coinstats_status,
    coinstats_wallet,
)
from libbndl import libbndl_from_arg, libbndl_overview
from execution_apis import (
    NAMESPACES as EXECUTION_NAMESPACES,
    execution_apis_method,
    execution_apis_overview,
    execution_from_arg,
)
from etherscan_stats import etherscan_stats_from_arg
from local_notes import recall_notes, remember_note
from network_tools import chain_tip_height, difficulty_adjustment, lookup_transaction, recommended_fees
from receive_check import check_receive, classify_payment_id

_TXID = re.compile(r"\b([0-9a-fA-F]{64})\b")
_ETH = re.compile(r"\b(0x[0-9a-fA-F]{40})\b")
_HELP = """Commands (no AWS required):
  rpc <name>          Look up a JSON-RPC method
  list [category]     List RPC methods
  docs <query>        Search Bitcoin Core markdown docs
  howto <topic>       build | test | contribute | rpc | agent | local | receive | wallet | agentic | jupiter | phantom | coinstats | libbndl | apko | execution | etherscan-stats
  wallet              How a payment arrives in a Bitcoin wallet
  agentic [status]    OKX Agentic Wallet overview, or onchainos CLI status
  jupiter [price|token|verify|status]  Jupiter overview, prices, search, VRFD eligibility, or jup CLI
  phantom [packages|status]  Phantom Connect SDK overview, npm versions, or phantom CLI
  coinstats [coin|markets|portfolio|wallet|status]  CoinStats MCP/REST overview, prices, portfolio, wallet
  libbndl [inspect|lookup|types|extract|create|add|replace|fetch]  BUNDLE inspect/extract/save/fetch
  apko [plan|status|preflight|run]  APKO smoke plan / Docker preflight (actions@7eaff21e)
  execution [method|list|graphql|contribute]  Ethereum Execution APIs spec (OpenRPC JSON-RPC + GraphQL)
  etherscan-stats [snapshot|supply|price|nodes|gas|status]  Etherscan charts/stats (needs ETHERSCAN_API_KEY)
  fees                Recommended fees from mempool.space
  tip                 Current chain tip height
  difficulty          Difficulty-adjustment estimate
  tx <txid>           Public transaction lookup
  source <0xaddr> [chain]  Verified EVM contract source (needs ETHERSCAN_API_KEY)
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


def _looks_like_agentic(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(agentic wallet|okx wallet|onchainos|x402|"
            r"agentic-wallet|okx agentic)\b",
            lower,
        )
    )


def _looks_like_jupiter(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(jupiter|jup|jup\.ag|jup-ag|vrfd|verified\.jup)\b",
            lower,
        )
    )


def _looks_like_phantom(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(phantom connect|phantom-connect|phantom sdk|"
            r"@phantom/|docs\.phantom\.com|phantom\.com/portal|"
            r"react-sdk|browser-sdk|react-native-sdk)\b",
            lower,
        )
    )


def _looks_like_coinstats(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(coinstats|coin-stats|coin stats|mcp\.coinstats|"
            r"coinstats\.app)\b",
            lower,
        )
    )


def _coinstats_from_arg(text: str) -> str:
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw or lower in {"overview", "help", "docs", "mcp", "ai"}:
        return coinstats_overview()
    if re.search(r"^(status|key|auth)\b", lower):
        return coinstats_status()
    if re.search(r"^(markets?|global|dominance|mcap|marketcap)\b", lower):
        return coinstats_markets()
    list_match = re.match(r"^portfolio\s+(list|ls|portfolios)\b", raw, re.I)
    if list_match or re.match(r"^(list|portfolios)\b", raw, re.I):
        return coinstats_portfolio_list()
    portfolio_match = re.match(r"^portfolio\b(?:\s+(.*))?$", raw, re.I)
    if portfolio_match:
        rest = (portfolio_match.group(1) or "").strip()
        if rest.lower() in {"list", "ls", "portfolios"}:
            return coinstats_portfolio_list()
        return coinstats_portfolio(rest)
    wallet_match = re.match(r"^wallet\b(?:\s+(.*))?$", raw, re.I)
    if wallet_match:
        rest = (wallet_match.group(1) or "").strip()
        parts = rest.split()
        address = parts[0] if parts else ""
        chain = parts[1] if len(parts) > 1 else ""
        return coinstats_wallet(address, chain)
    coin_match = re.match(r"^(coin|price|quote)\b(?:\s+(.*))?$", raw, re.I)
    if coin_match:
        return coinstats_coin(coin_match.group(2) or "")
    if re.search(r"\b(status|api key|apikey)\b", lower) and not re.search(
        r"\b(coin|price|portfolio|wallet|market)\b", lower
    ):
        return coinstats_status()
    if re.search(r"\b(market|markets|dominance|mcap)\b", lower):
        return coinstats_markets()
    if re.search(r"\b(portfolio|portfolios|pnl|p/l|holdings)\b", lower):
        if re.search(r"\b(list|ls)\b", lower):
            return coinstats_portfolio_list()
        rest = re.sub(
            r"\b(portfolio|portfolios|pnl|p/l|holdings|coins?|for|of|the|my)\b",
            " ",
            raw,
            flags=re.I,
        )
        return coinstats_portfolio(rest)
    if re.search(r"\b(wallet|balance|address)\b", lower):
        rest = re.sub(
            r"\b(wallet|balance|address|for|of|the|on)\b",
            " ",
            raw,
            flags=re.I,
        )
        parts = rest.split()
        address = parts[0] if parts else ""
        chain = parts[1] if len(parts) > 1 else ""
        return coinstats_wallet(address, chain)
    if raw and not re.search(r"\b(how|what|docs|skill|mcp|cli)\b", lower):
        return coinstats_coin(raw)
    return coinstats_overview()


def _looks_like_libbndl(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(libbndl|libapt2|bndl|bnd2|bundle archive|burnout paradise)\b",
            lower,
        )
    )


def _looks_like_apko(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(apko|melange|ubuntu-slim|smoke test|smoke_test|images\.apko)\b",
            lower,
        )
    )


_EXECUTION_METHOD = re.compile(
    r"\b((?:eth|engine|debug|txpool|net|testing|web3)_[A-Za-z0-9]+)\b",
    re.I,
)


def _looks_like_etherscan_stats(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(etherscan-stats|ethstats|etherscan stats|"
            r"etherscan\.io/charts|etherscan\.io/statscharts|"
            r"ethsupply2?|ethprice|nodecount|gasoracle)\b",
            lower,
        )
    ) or bool(
        re.search(r"\betherscan\b", lower)
        and re.search(r"\b(stat|chart|supply|price|nodes?|gas|oracle)\b", lower)
    )


def _etherscan_command(arg: str) -> str:
    raw = (arg or "").strip()
    if _ETH.search(raw):
        return _contract_source_from_arg(raw)
    if re.search(r"\b(source|getsourcecode|contract)\b", raw, re.I):
        return _contract_source_from_arg(raw)
    return etherscan_stats_from_arg(raw)


def _looks_like_execution(lower: str) -> bool:
    if _EXECUTION_METHOD.search(lower):
        return True
    return bool(
        re.search(
            r"\b(execution-apis|execution apis|execution api|"
            r"ethereum json-rpc|ethereum rpc|openrpc|"
            r"engine api|eip-1767|hive rpc-compat|"
            r"ethereum\.github\.io/execution-apis)\b",
            lower,
        )
    )


def _jupiter_from_arg(text: str) -> str:
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw or lower in {"overview", "help", "docs", "ai"}:
        return jupiter_overview()
    if re.search(r"^(status|cli|version)\b", lower):
        return jupiter_cli_status()
    price_match = re.match(r"^(price|quote)\b(?:\s+(.*))?$", raw, re.I)
    if price_match:
        return jupiter_price(price_match.group(2) or "")
    verify_match = re.match(
        r"^(verify|verification|eligibility|eligible|vrfd|express)\b(?:\s+(.*))?$",
        raw,
        re.I,
    )
    if verify_match:
        return jupiter_verify_eligibility(verify_match.group(2) or "")
    token_match = re.match(r"^(token|tokens|search)\b(?:\s+(.*))?$", raw, re.I)
    if token_match:
        return jupiter_token_search(token_match.group(2) or "")
    if re.search(r"\b(status|installed|version|cli)\b", lower) and not re.search(
        r"\b(price|token|search|quote|verify|eligibility)\b", lower
    ):
        return jupiter_cli_status()
    if re.search(r"\b(price|quote|usd)\b", lower):
        rest = re.sub(r"\b(price|quote|usd|of|for|on|the)\b", " ", raw, flags=re.I)
        return jupiter_price(rest)
    if re.search(r"\b(verify|verification|eligibility|eligible|vrfd|express)\b", lower):
        rest = re.sub(
            r"\b(verify|verification|eligibility|eligible|vrfd|express|check|"
            r"for|of|on|the|can|i|we|this|token|tokens|mint)\b",
            " ",
            raw,
            flags=re.I,
        )
        return jupiter_verify_eligibility(rest)
    if re.search(r"\b(token|tokens|search|mint)\b", lower):
        rest = re.sub(r"\b(token|tokens|search|mint|for|of)\b", " ", raw, flags=re.I)
        return jupiter_token_search(rest)
    # Bare symbols / mints after `jupiter`: treat as a price lookup.
    if raw and not re.search(r"\b(how|what|docs|skill|mcp|cli)\b", lower):
        return jupiter_price(raw)
    return jupiter_overview()


def _phantom_from_arg(text: str) -> str:
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw or lower in {"overview", "help", "docs", "sdk", "connect"}:
        return phantom_connect_overview()
    if re.search(r"^(status|cli|version)\b", lower):
        return phantom_connect_cli_status()
    packages_match = re.match(
        r"^(packages?|npm|versions)\b(?:\s+(.*))?$",
        raw,
        re.I,
    )
    if packages_match:
        return phantom_connect_packages(packages_match.group(2) or "")
    if re.search(r"\b(status|installed|cli)\b", lower) and not re.search(
        r"\b(package|packages|npm|react|browser)\b", lower
    ):
        return phantom_connect_cli_status()
    if re.search(r"\b(package|packages|npm|react-sdk|browser-sdk|react-native)\b", lower):
        rest = re.sub(
            r"\b(package|packages|npm|latest|version|versions|of|for|the)\b",
            " ",
            raw,
            flags=re.I,
        )
        return phantom_connect_packages(rest)
    return phantom_connect_overview()


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


def _looks_like_contract_source(lower: str) -> bool:
    return bool(
        re.search(
            r"\b(source code|verified source|getsourcecode|contract source|"
            r"verified contract|solidity source)\b",
            lower,
        )
    )


def _contract_source_from_arg(text: str) -> str:
    address = ""
    chain = "1"
    for token in re.findall(r"[A-Za-z0-9=]+", text or ""):
        if classify_payment_id(token) == "ethereum":
            address = token
        elif normalize_chain_id(token) is not None and token.lower() not in {
            "source",
            "contract",
            "getsourcecode",
            "on",
        }:
            chain = token
    if not address:
        return (
            "Provide a contract address: source <0xaddress> [chainid]. "
            "Example: source 0xdAC17F958D2ee523a2206206994597C13D831ec7"
        )
    return lookup_contract_source(address, chain)


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
        "agentic": lambda: agentic_wallet_status() if re.search(r"\b(status|cli)\b", arg.lower()) else agentic_wallet_overview(),
        "agentic-wallet": lambda: agentic_wallet_status() if re.search(r"\b(status|cli)\b", arg.lower()) else agentic_wallet_overview(),
        "jupiter": lambda: _jupiter_from_arg(arg),
        "jup": lambda: _jupiter_from_arg(arg),
        "phantom": lambda: _phantom_from_arg(arg),
        "phantom-connect": lambda: _phantom_from_arg(arg),
        "coinstats": lambda: _coinstats_from_arg(arg),
        "coin-stats": lambda: _coinstats_from_arg(arg),
        "libbndl": lambda: libbndl_from_arg(arg),
        "bndl": lambda: libbndl_from_arg(arg),
        "bnd2": lambda: libbndl_from_arg(arg),
        "apko": lambda: apko_from_arg(arg),
        "melange": lambda: apko_from_arg(arg),
        "execution": lambda: execution_from_arg(arg),
        "execution-apis": lambda: execution_from_arg(arg),
        "executionapis": lambda: execution_from_arg(arg),
        "ethrpc": lambda: execution_from_arg(arg),
        "etherscan-stats": lambda: etherscan_stats_from_arg(arg),
        "ethstats": lambda: etherscan_stats_from_arg(arg),
        "etherscan": lambda: _etherscan_command(arg),
        "fees": recommended_fees,
        "tip": chain_tip_height,
        "height": chain_tip_height,
        "difficulty": difficulty_adjustment,
        "tx": lambda: lookup_transaction(arg),
        "source": lambda: _contract_source_from_arg(arg),
        "contract": lambda: _contract_source_from_arg(arg),
        "getsourcecode": lambda: _contract_source_from_arg(arg),
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
    eth = _ETH.search(raw)
    if eth and _looks_like_contract_source(lower):
        return _contract_source_from_arg(raw)
    if _looks_like_agentic(lower):
        if re.search(r"\b(status|installed|logged[- ]in|am i signed)\b", lower):
            return agentic_wallet_status()
        return agentic_wallet_overview()
    if _looks_like_jupiter(lower):
        rest = re.sub(
            r"\b(jupiter|jup\.ag|jup-ag|vrfd|verified\.jup)\b",
            " ",
            raw,
            flags=re.I,
        )
        return _jupiter_from_arg(rest)
    if _looks_like_phantom(lower):
        rest = re.sub(
            r"\b(phantom connect|phantom-connect|phantom sdk|phantom|"
            r"@phantom/|docs\.phantom\.com|phantom\.com/portal)\b",
            " ",
            raw,
            flags=re.I,
        )
        return _phantom_from_arg(rest)
    if _looks_like_coinstats(lower):
        rest = re.sub(
            r"\b(coinstats|coin-stats|coin stats|mcp\.coinstats|"
            r"coinstats\.app)\b",
            " ",
            raw,
            flags=re.I,
        )
        return _coinstats_from_arg(rest)
    if _looks_like_libbndl(lower):
        rest = re.sub(
            r"\b(libbndl|libapt2|bundle archive|burnout paradise)\b",
            " ",
            raw,
            flags=re.I,
        )
        if re.search(r"\b(inspect|lookup|list|extract|create|add|replace|fetch|types)\b", rest, re.I) or re.search(
            r"\.(bndl|bnd2|bundle)\b", rest, re.I
        ) or re.search(r"https?://", rest, re.I):
            return libbndl_from_arg(rest)
        return libbndl_overview()
    if _looks_like_apko(lower):
        rest = re.sub(r"\b(apko|melange)\b", " ", raw, flags=re.I)
        if re.search(r"\b(plan|status|preflight|pull|run|smoke|matrix|daemon)\b", rest, re.I) or rest.strip().endswith(
            ".json"
        ):
            return apko_from_arg(rest)
        return apko_smoke_overview()
    if cmd.split("_", 1)[0] in EXECUTION_NAMESPACES and "_" in cmd:
        return execution_apis_method(raw)
    if _looks_like_etherscan_stats(lower):
        rest = re.sub(
            r"\b(etherscan-stats|ethstats|etherscan stats|etherscan|"
            r"etherscan\.io/charts|etherscan\.io/statscharts)\b",
            " ",
            raw,
            flags=re.I,
        )
        return etherscan_stats_from_arg(rest)
    if _looks_like_execution(lower):
        rest = re.sub(
            r"\b(execution-apis|execution apis|execution api|execution|"
            r"ethereum json-rpc|ethereum rpc|openrpc|"
            r"engine api)\b",
            " ",
            raw,
            flags=re.I,
        )
        token = _EXECUTION_METHOD.search(raw)
        if token and not re.search(r"\b(list|graphql|contribute|quickstart)\b", rest, re.I):
            return execution_apis_method(token.group(1))
        if rest.strip() or token:
            return execution_from_arg(rest)
        return execution_apis_overview()
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
        "agentic": "agentic",
        "okx": "agentic",
        "jupiter": "jupiter",
        "jup-ag": "jupiter",
        "phantom": "phantom",
        "phantom-connect": "phantom",
        "coinstats": "coinstats",
        "coin-stats": "coinstats",
        "libbndl": "libbndl",
        "bndl": "libbndl",
        "bundle": "libbndl",
        "apko": "apko",
        "melange": "apko",
        "ubuntu-slim": "apko",
        "execution": "execution",
        "execution-apis": "execution",
        "openrpc": "execution",
        "engine-api": "execution",
        "etherscan-stats": "etherscan-stats",
        "ethstats": "etherscan-stats",
        "etherscan-statistics": "etherscan-stats",
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
