"""Read-only Etherscan charts-and-stats lookups.

HTTPS GET to api.etherscan.io v2, module=stats (plus gastracker/gasoracle).
Requires ETHERSCAN_API_KEY. Never logs the key, never broadcasts, and
never calls PRO daily-chart endpoints.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from contract_source import etherscan_get, normalize_chain_id
from mcp_client.settings import etherscan_api_key
from optional_tool import tool

KEY_URL = "https://etherscan.io/apidashboard"
CHARTS_URL = "https://etherscan.io/charts"
STATS_CHARTS_URL = "https://etherscan.io/statscharts"
SHOWCASE_URL = "https://docs.etherscan.io/endpoint-showcase/charts-and-stats"
SUPPLY2_DOCS_URL = "https://docs.etherscan.io/api-reference/endpoint/ethsupply2"
PRICE_DOCS_URL = "https://docs.etherscan.io/api-reference/endpoint/ethprice"
NODES_DOCS_URL = "https://docs.etherscan.io/api-reference/endpoint/nodecount"
GAS_DOCS_URL = "https://docs.etherscan.io/api-reference/endpoint/gasoracle"
MCP_URL = "https://mcp.etherscan.io/mcp"
DOCS_MCP_URL = "https://docs.etherscan.io/mcp"
BUILD_WITH_AI_URL = "https://docs.etherscan.io/build-with-ai/introduction"
CLI_DOCS_URL = "https://docs.etherscan.io/build-with-ai/cli"
CLI_PACKAGE = "@etherscan/cli"
CLI_COMMAND = "npx -y @etherscan/cli"
WEI_PER_ETH = 10**18
_ALLOWED_ACTIONS = {
    ("stats", "ethsupply"),
    ("stats", "ethsupply2"),
    ("stats", "ethprice"),
    ("stats", "nodecount"),
    ("gastracker", "gasoracle"),
}
_PRO_ACTIONS = (
    "dailytx",
    "dailynewaddress",
    "dailygasused",
    "ethdailyprice",
    "dailyblkcount",
    "nodecounthistory",
    "dailytxnfee",
    "dailynetutilization",
)
_SECRET_TOKENS = (
    "seed",
    "xprv",
    "private",
    "secret key",
    "api key",
    "mnemonic",
    "recovery phrase",
)
_ETH_ADDRESS = re.compile(r"\b(0x[0-9a-fA-F]{40})\b")
_MISSING_KEY = (
    "Set ETHERSCAN_API_KEY to read Etherscan charts and stats "
    f"({KEY_URL}). Create a free key, export it in the environment, "
    "then retry. This tool is read-only and counts against your Etherscan quota."
)
_CHAIN_LABELS = {
    "1": "Ethereum",
    "10": "Optimism",
    "56": "BNB Smart Chain",
    "137": "Polygon",
    "8453": "Base",
    "42161": "Arbitrum",
    "43114": "Avalanche",
    "11155111": "Sepolia",
}


def _secret_query(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _SECRET_TOKENS)


def allowed_stats_action(module: str, action: str) -> bool:
    """Return True when this is a free, read-only stats/gas GET."""
    return (module, action) in _ALLOWED_ACTIONS


def etherscan_stats_get(chain_id: str, module: str, action: str) -> Any:
    """Allowlisted GET for free stats / gas-oracle actions."""
    if not allowed_stats_action(module, action):
        raise ValueError("Refusing Etherscan stats action that is not on the allowlist.")
    return etherscan_get({"chainid": chain_id, "module": module, "action": action})


def _api_error(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return "Etherscan returned an unexpected payload."
    if payload.get("error"):
        return str(payload["error"])
    status = str(payload.get("status") or "")
    message = str(payload.get("message") or "")
    result = payload.get("result")
    if status == "0":
        if isinstance(result, str) and result.strip():
            return result.strip()
        return message.strip() or "Etherscan returned status 0."
    return None


def _format_eth_from_wei(value: Any) -> str:
    try:
        wei = int(str(value).strip())
    except (TypeError, ValueError):
        return str(value)
    eth = wei / WEI_PER_ETH
    if abs(eth) >= 1:
        return f"{eth:,.4f}".rstrip("0").rstrip(".")
    return f"{eth:.8f}".rstrip("0").rstrip(".")


def _format_number(value: Any, *, places: int = 4) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1:
        text = f"{number:,.{places}f}".rstrip("0").rstrip(".")
        return text or "0"
    return f"{number:.8f}".rstrip("0").rstrip(".")


def _format_unix(value: Any) -> str:
    try:
        stamp = int(value)
    except (TypeError, ValueError):
        return str(value)
    return datetime.fromtimestamp(stamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _chain_label(chain_id: str) -> str:
    name = _CHAIN_LABELS.get(chain_id)
    return f"{name} (chainid {chain_id})" if name else f"chainid {chain_id}"


def _resolve_chain(chainid: str) -> str | None:
    return normalize_chain_id(chainid)


def _overview_text() -> str:
    return (
        "Etherscan charts and statistics are the same numbers behind "
        f"{CHARTS_URL} / {STATS_CHARTS_URL}, served by API v2 module=stats.\n"
        "\n"
        "This agent is read-only and free-tier only:\n"
        f"- supply: ethsupply2 (circulation, staking, burned, withdrawn) — {SUPPLY2_DOCS_URL}\n"
        f"- price: ethprice (native token vs USD/BTC) — {PRICE_DOCS_URL}\n"
        f"- nodes: nodecount — {NODES_DOCS_URL}\n"
        f"- gas: gastracker/gasoracle (safe / proposed / fast) — {GAS_DOCS_URL}\n"
        f"- snapshot: those four together\n"
        "\n"
        "This agent does not call PRO daily chart endpoints "
        f"({', '.join(_PRO_ACTIONS)}). Use a paid plan or "
        f"{SHOWCASE_URL} on a machine you control.\n"
        "\n"
        f"Needs ETHERSCAN_API_KEY ({KEY_URL}). The key is never printed. "
        f"Cursor already has official MCP at {MCP_URL} and docs MCP at "
        f"{DOCS_MCP_URL} (Build with AI: {BUILD_WITH_AI_URL}).\n"
        "\n"
        "Official CLI (on a machine you control; not attached here):\n"
        f"  npm install -g {CLI_PACKAGE} && etherscan login\n"
        "  etherscan stats ethsupply2\n"
        "  etherscan stats ethprice\n"
        "  etherscan stats nodecount\n"
        "  etherscan gastracker oracle\n"
        "\n"
        "Local:\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats snapshot\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats supply\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats price base\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats nodes\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats gas\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats status\n"
        "\n"
        "Not Bitcoin Core chain stats — those stay on `fees`, `tip`, and "
        "`difficulty`. Verified contract source stays on `source` / "
        "lookup_contract_source."
    )


def _format_supply_result(result: Any, chain_id: str) -> str:
    if isinstance(result, str) and result.strip().isdigit():
        return (
            f"Etherscan ETH circulating supply ({_chain_label(chain_id)}):\n"
            f"- ethsupply: {_format_eth_from_wei(result)} ETH "
            "(excludes staking rewards and EIP-1559 burned fees)\n"
            "Read-only. This agent will not send or stake."
        )
    if not isinstance(result, dict):
        return "Etherscan supply returned an unexpected payload."
    lines = [
        f"Etherscan ETH supply ({_chain_label(chain_id)}):",
        f"- EthSupply: {_format_eth_from_wei(result.get('EthSupply'))} ETH "
        "(block rewards, wei from ethsupply2)",
        f"- Eth2Staking: {_format_eth_from_wei(result.get('Eth2Staking'))} ETH",
        f"- BurntFees: {_format_eth_from_wei(result.get('BurntFees'))} ETH (EIP-1559)",
        f"- WithdrawnTotal: {_format_eth_from_wei(result.get('WithdrawnTotal'))} ETH",
        f"Docs: {SUPPLY2_DOCS_URL}",
        "Read-only. This agent will not send or stake.",
    ]
    return "\n".join(lines)


def _format_price_result(result: Any, chain_id: str) -> str:
    if not isinstance(result, dict):
        return "Etherscan price returned an unexpected payload."
    usd_at = result.get("ethusd_timestamp")
    btc_at = result.get("ethbtc_timestamp")
    lines = [
        f"Etherscan native-token price ({_chain_label(chain_id)}):",
        f"- USD: ${_format_number(result.get('ethusd'))}",
        f"- BTC: {_format_number(result.get('ethbtc'), places=8)}",
    ]
    if usd_at:
        lines.append(f"- USD quote: {_format_unix(usd_at)}")
    if btc_at and btc_at != usd_at:
        lines.append(f"- BTC quote: {_format_unix(btc_at)}")
    lines.append(f"Docs: {PRICE_DOCS_URL}")
    lines.append("Read-only. This agent will not trade.")
    return "\n".join(lines)


def _format_nodes_result(result: Any, chain_id: str) -> str:
    if not isinstance(result, dict):
        return "Etherscan node count returned an unexpected payload."
    count = result.get("TotalNodeCount")
    day = result.get("UTCDate") or "n/a"
    try:
        pretty = f"{int(str(count)):,}"
    except (TypeError, ValueError):
        pretty = str(count)
    return "\n".join(
        [
            f"Etherscan discoverable nodes ({_chain_label(chain_id)}):",
            f"- TotalNodeCount: {pretty}",
            f"- UTCDate: {day}",
            f"Docs: {NODES_DOCS_URL}",
            "Read-only. This agent will not run or advertise a node.",
        ]
    )


def _format_gas_result(result: Any, chain_id: str) -> str:
    if not isinstance(result, dict):
        return "Etherscan gas oracle returned an unexpected payload."
    lines = [
        f"Etherscan gas oracle ({_chain_label(chain_id)}):",
        f"- SafeGasPrice: {_format_number(result.get('SafeGasPrice'))} gwei",
        f"- ProposeGasPrice: {_format_number(result.get('ProposeGasPrice'))} gwei",
        f"- FastGasPrice: {_format_number(result.get('FastGasPrice'))} gwei",
        f"- suggestBaseFee: {_format_number(result.get('suggestBaseFee'))} gwei",
        f"- LastBlock: {result.get('LastBlock', 'n/a')}",
    ]
    ratio = str(result.get("gasUsedRatio") or "").strip()
    if ratio:
        first = ratio.split(",")[0]
        lines.append(f"- latest gasUsedRatio: {_format_number(first)}")
    lines.append(f"Docs: {GAS_DOCS_URL}")
    lines.append("Read-only. This agent will not send a transaction.")
    return "\n".join(lines)


def _lookup(chainid: str, module: str, action: str) -> tuple[str | None, Any]:
    if _secret_query(chainid or ""):
        return "Do not paste seed phrases, private keys, or API keys.", None
    chain_id = _resolve_chain(chainid)
    if chain_id is None:
        return (
            "chainid must be a numeric Etherscan chain ID (for example 1) or a "
            "known name such as ethereum, arbitrum, or base. "
            "See https://docs.etherscan.io/supported-chains.",
            None,
        )
    if not etherscan_api_key():
        return _MISSING_KEY, None
    payload = etherscan_stats_get(chain_id, module, action)
    error = _api_error(payload)
    if error:
        return error, None
    return None, (chain_id, payload.get("result") if isinstance(payload, dict) else None)


_METRIC_WORDS = {
    "snapshot",
    "stats",
    "all",
    "overview-live",
    "supply",
    "ethsupply",
    "ethsupply2",
    "circulation",
    "price",
    "ethprice",
    "usd",
    "quote",
    "nodes",
    "node",
    "nodecount",
    "peers",
    "gas",
    "oracle",
    "gasoracle",
    "gastracker",
}


def _split_metric_and_chain(text: str) -> tuple[str, str]:
    raw = (text or "").strip()
    if not raw:
        return "", "1"
    parts = raw.split()
    if len(parts) == 1:
        token = parts[0]
        if token.lower() in _METRIC_WORDS:
            return token, "1"
        if normalize_chain_id(token) is not None:
            return "", token
        return token, "1"
    metric = parts[0]
    rest = parts[1:]
    chain = "1"
    leftover: list[str] = []
    for token in rest:
        if normalize_chain_id(token) is not None and token.lower() not in _METRIC_WORDS:
            chain = token
        else:
            leftover.append(token)
    if leftover and metric.lower() not in _METRIC_WORDS:
        return "", chain
    return metric, chain


@tool
def etherscan_stats_overview() -> str:
    """Explain Etherscan charts/stats pages and the free read-only API tools.

    Does not call PRO daily endpoints or attach the official CLI.
    """
    return _overview_text()


@tool
def etherscan_eth_supply(chainid: str = "1") -> str:
    """Current ETH supply breakdown from Etherscan stats/ethsupply2.

    Circulation, beacon staking, EIP-1559 burned fees, and withdrawals.
    Pass chainid as a number or name (ethereum, arbitrum, base). Needs
    ETHERSCAN_API_KEY. Read-only; does not send or stake.
    """
    error, data = _lookup(chainid, "stats", "ethsupply2")
    if error:
        return error
    assert data is not None
    chain_id, result = data
    return _format_supply_result(result, chain_id)


@tool
def etherscan_eth_price(chainid: str = "1") -> str:
    """Latest native-token price (USD and BTC) from Etherscan stats/ethprice.

    Needs ETHERSCAN_API_KEY. Read-only; does not trade.
    """
    error, data = _lookup(chainid, "stats", "ethprice")
    if error:
        return error
    assert data is not None
    chain_id, result = data
    return _format_price_result(result, chain_id)


@tool
def etherscan_node_count(chainid: str = "1") -> str:
    """Discoverable node count from Etherscan stats/nodecount.

    Needs ETHERSCAN_API_KEY. Read-only; does not run a node.
    """
    error, data = _lookup(chainid, "stats", "nodecount")
    if error:
        return error
    assert data is not None
    chain_id, result = data
    return _format_nodes_result(result, chain_id)


@tool
def etherscan_gas_oracle(chainid: str = "1") -> str:
    """Safe / proposed / fast gas prices from Etherscan gastracker/gasoracle.

    Needs ETHERSCAN_API_KEY. Read-only; does not send a transaction.
    """
    error, data = _lookup(chainid, "gastracker", "gasoracle")
    if error:
        return error
    assert data is not None
    chain_id, result = data
    return _format_gas_result(result, chain_id)


@tool
def etherscan_stats(chainid: str = "1") -> str:
    """Free Etherscan stats snapshot: supply, price, nodes, and gas oracle.

    The numbers behind etherscan.io/charts. Needs ETHERSCAN_API_KEY.
    Does not call PRO daily-chart endpoints. Read-only.
    """
    if _secret_query(chainid or ""):
        return "Do not paste seed phrases, private keys, or API keys."
    chain_id = _resolve_chain(chainid)
    if chain_id is None:
        return (
            "chainid must be a numeric Etherscan chain ID (for example 1) or a "
            "known name such as ethereum, arbitrum, or base. "
            "See https://docs.etherscan.io/supported-chains."
        )
    if not etherscan_api_key():
        return _MISSING_KEY

    sections: list[str] = [f"Etherscan statistics snapshot ({_chain_label(chain_id)}):"]
    jobs = (
        ("supply", "stats", "ethsupply2", _format_supply_result),
        ("price", "stats", "ethprice", _format_price_result),
        ("nodes", "stats", "nodecount", _format_nodes_result),
        ("gas", "gastracker", "gasoracle", _format_gas_result),
    )
    for label, module, action, formatter in jobs:
        payload = etherscan_stats_get(chain_id, module, action)
        error = _api_error(payload)
        if error:
            sections.append(f"\n## {label}\n{error}")
            continue
        result = payload.get("result") if isinstance(payload, dict) else None
        body = formatter(result, chain_id)
        sections.append(f"\n## {label}\n{body}")
    sections.append(
        f"\nCharts: {CHARTS_URL}\n"
        "Read-only free-tier snapshot. PRO daily charts are not fetched. "
        "This agent will not send, stake, or trade."
    )
    return "\n".join(sections)


@tool
def etherscan_stats_status() -> str:
    """Report whether ETHERSCAN_API_KEY is set. Never prints the key."""
    if etherscan_api_key():
        key_state = "set (not printed; used as apikey= on api.etherscan.io)"
    else:
        key_state = f"unset — stats tools stay off until you export a key from {KEY_URL}"
    return (
        "Etherscan statistics status:\n"
        f"- ETHERSCAN_API_KEY: {key_state}\n"
        f"- Cursor MCP: {MCP_URL} (Bearer; already in .cursor/mcp.json)\n"
        f"- Charts: {CHARTS_URL}\n"
        f"- Official CLI (not attached): {CLI_COMMAND}\n"
        "Read-only here. This agent will not call PRO daily endpoints or send."
    )


def etherscan_stats_from_arg(text: str) -> str:
    """Map a local CLI argument onto a stats tool."""
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw or lower in {"overview", "help", "docs", "charts", "mcp", "ai"}:
        return etherscan_stats_overview()
    if re.search(r"^(status|key|auth)\b", lower):
        return etherscan_stats_status()
    if re.search(r"\b(how|what|docs|skill|mcp|cli|explain)\b", lower) and not re.search(
        r"\b(snapshot|supply|price|nodes?|gas|oracle|status)\b", lower
    ):
        return etherscan_stats_overview()
    if _ETH_ADDRESS.search(raw):
        return (
            "Contract source is a different tool. Use "
            "`source <0xaddress> [chain]`, not etherscan-stats."
        )
    if any(token in lower for token in _PRO_ACTIONS) or re.search(
        r"\b(daily|pro chart|history)\b", lower
    ):
        return (
            "PRO daily chart endpoints are not called here "
            f"({', '.join(_PRO_ACTIONS)}). Use a paid Etherscan plan or "
            f"{SHOWCASE_URL}."
        )

    metric, chain = _split_metric_and_chain(raw)
    metric_l = metric.lower()
    if metric_l in {"", "snapshot", "stats", "all", "overview-live"}:
        return etherscan_stats(chain or "1")
    if metric_l in {"supply", "ethsupply", "ethsupply2", "circulation"}:
        return etherscan_eth_supply(chain)
    if metric_l in {"price", "ethprice", "usd", "quote"}:
        return etherscan_eth_price(chain)
    if metric_l in {"nodes", "node", "nodecount", "peers"}:
        return etherscan_node_count(chain)
    if metric_l in {"gas", "oracle", "gasoracle", "gastracker"}:
        return etherscan_gas_oracle(chain)

    if re.search(r"\b(status|api key|apikey)\b", lower):
        return etherscan_stats_status()
    if re.search(r"\b(supply|ethsupply|stak|burn)\b", lower):
        rest = re.sub(
            r"\b(supply|ethsupply2?|ether|eth|circulation|stak\w*|burn\w*|for|of|on|the)\b",
            " ",
            raw,
            flags=re.I,
        )
        return etherscan_eth_supply(rest.strip() or "1")
    if re.search(r"\b(price|usd|quote|ethprice)\b", lower):
        rest = re.sub(
            r"\b(price|usd|quote|ethprice|ether|eth|for|of|on|the)\b",
            " ",
            raw,
            flags=re.I,
        )
        return etherscan_eth_price(rest.strip() or "1")
    if re.search(r"\b(node|nodes|nodecount|peers)\b", lower):
        rest = re.sub(
            r"\b(nodes?|nodecount|peers|count|for|of|on|the)\b",
            " ",
            raw,
            flags=re.I,
        )
        return etherscan_node_count(rest.strip() or "1")
    if re.search(r"\b(gas|oracle|gwei)\b", lower):
        rest = re.sub(
            r"\b(gas|oracle|gasoracle|gastracker|gwei|for|of|on|the)\b",
            " ",
            raw,
            flags=re.I,
        )
        return etherscan_gas_oracle(rest.strip() or "1")
    if raw and normalize_chain_id(raw) is not None:
        return etherscan_stats(raw)
    return etherscan_stats_overview()
