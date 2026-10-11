"""Read-only CoinStats market / portfolio / wallet lookups.

REST is HTTPS GET to api.coinstats.app with an optional COINSTATS_API_KEY
(X-API-KEY). Cursor uses the hosted MCP at mcp.coinstats.app via OAuth.

This module never adds transactions, connects wallets or exchanges,
syncs, or deletes portfolios. Those write MCP tools stay off.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp_client.settings import coinstats_api_key
from optional_tool import tool
from receive_check import classify_payment_id

COINSTATS_API_HOST = "api.coinstats.app"
MCP_URL = "https://mcp.coinstats.app/mcp"
CONNECT_URL = "https://coinstats.app/api-docs/mcp/connecting/"
TOOLS_URL = "https://coinstats.app/api-docs/mcp/tools/"
LLMS_TXT_URL = "https://coinstats.app/docs/llms.txt"
DOCS_URL = "https://coinstats.app/api-docs/"
DASHBOARD_URL = "https://openapi.coinstats.app"
LANDING_URL = "https://coinstats.app/mcp/"
STDIO_PACKAGE = "@coinstats/coinstats-mcp"
STDIO_COMMAND = "npx -y @coinstats/coinstats-mcp"
_ALLOWED_HOSTS = {COINSTATS_API_HOST}
_ALLOWED_PATHS = {
    "/v1/coins",
    "/v1/markets",
    "/v1/portfolio/list",
    "/v1/portfolio/coins",
    "/v1/wallet/balance",
}
_COIN_PATH_PREFIX = "/v1/coins/"
_TIMEOUT_SECONDS = 8
_WALLET_TIMEOUT_SECONDS = 20
_MAX_BYTES = 256_000
_MAX_PORTFOLIO_ROWS = 12
_MAX_WALLET_ROWS = 12
_COIN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_PORTFOLIO_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CHAIN = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
_FORBIDDEN_CHAINS = {"all", "forceall"}
_KNOWN_IDS: dict[str, str] = {
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "sol": "solana",
    "solana": "solana",
    "usdt": "tether",
    "tether": "tether",
    "usdc": "usd-coin",
    "usd-coin": "usd-coin",
    "usdcoin": "usd-coin",
    "xrp": "ripple",
    "ripple": "ripple",
    "doge": "dogecoin",
    "dogecoin": "dogecoin",
    "ada": "cardano",
    "cardano": "cardano",
    "bnb": "binance-coin",
    "binance-coin": "binance-coin",
    "avax": "avalanche",
    "avalanche": "avalanche",
    "matic": "polygon",
    "polygon": "polygon",
    "link": "chainlink",
    "chainlink": "chainlink",
    "jup": "jupiter",
    "jupiter": "jupiter",
}
_STOPWORDS = {
    "a",
    "about",
    "and",
    "coin",
    "coinstats",
    "crypto",
    "currency",
    "for",
    "id",
    "lookup",
    "market",
    "of",
    "on",
    "price",
    "show",
    "stats",
    "the",
    "what",
}


def _overview_text() -> str:
    return (
        "CoinStats is a crypto market-data and portfolio platform. "
        "The hosted MCP server is Streamable HTTP + OAuth 2.1.\n"
        "\n"
        "Read the docs:\n"
        f"- MCP landing: {LANDING_URL}\n"
        f"- Connect (OAuth): {CONNECT_URL}\n"
        f"- Tool catalog: {TOOLS_URL}\n"
        f"- llms.txt index: {LLMS_TXT_URL}\n"
        f"- REST: {DOCS_URL}\n"
        "\n"
        f"Cursor is already wired in .cursor/mcp.json as coinstats "
        f"({MCP_URL}). Restart Cursor; the first call opens a browser "
        "consent page. No API key is required for that OAuth path.\n"
        "\n"
        "This agent is read-only: overview, coin prices, global market "
        "cap, your portfolio list / coins + PnL, and a public wallet "
        "balance. REST calls need COINSTATS_API_KEY "
        f"({DASHBOARD_URL}), sent as X-API-KEY and never logged.\n"
        "\n"
        "Write MCP tools are not attached: add-portfolio-transaction, "
        "connect-portfolio-wallet, connect-portfolio-exchange, "
        "sync-portfolio, delete-portfolio. AgentCore Gateway cannot "
        "complete browser OAuth, so the runtime talks to "
        "api.coinstats.app directly.\n"
        "\n"
        "Headless stdio MCP (on a machine you control; still has writes):\n"
        f"  export COINSTATS_API_KEY=… && {STDIO_COMMAND}\n"
        "\n"
        "Local:\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats coin bitcoin\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats markets\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats portfolio\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats wallet <addr> bitcoin\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats status\n"
        f"Docs: {DOCS_URL}"
    )


def _secret_query(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "seed",
            "xprv",
            "private",
            "secret key",
            "api key",
            "passcode",
            "sharetoken",
            "share token",
        )
    )


def _missing_key_message(need: str) -> str:
    return (
        f"{need} needs COINSTATS_API_KEY "
        f"({DASHBOARD_URL}). Export it as X-API-KEY; it is never printed. "
        "Cursor can use the hosted MCP via OAuth without this key."
    )


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": "BitcoinAgent/1.0"}
    key = coinstats_api_key()
    if key:
        headers["X-API-KEY"] = key
    return headers


def _coin_path(coin_id: str) -> str:
    return f"{_COIN_PATH_PREFIX}{coin_id}"


def allowed_coinstats_path(path: str) -> bool:
    """Return True when path is an allowlisted GET."""
    if path in _ALLOWED_PATHS:
        return True
    if path.startswith(_COIN_PATH_PREFIX):
        rest = path[len(_COIN_PATH_PREFIX) :]
        return bool(_COIN_ID.match(rest))
    return False


def resolve_coin_id(text: str) -> str | None:
    """Map a symbol or CoinStats slug to a coinId, or None."""
    raw = (text or "").strip()
    if not raw or _secret_query(raw):
        return None
    token = raw.split()[0].strip(",./")
    if token.lower() in _STOPWORDS:
        return None
    alias = _KNOWN_IDS.get(token.lower())
    if alias:
        return alias
    slug = token.lower()
    if _COIN_ID.match(slug):
        return slug
    return None


def resolve_portfolio_id(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw or _secret_query(raw):
        return None
    if raw.lower() in {"all", "aggregate", "*"}:
        return ""
    if _PORTFOLIO_ID.match(raw):
        return raw
    return None


def _default_wallet_chain(address: str) -> str | None:
    kind = classify_payment_id(address)
    if kind == "bitcoin":
        return "bitcoin"
    if kind == "ethereum":
        return "ethereum"
    return None


def resolve_wallet_chain(text: str) -> str | None:
    raw = (text or "").strip().lower()
    if not raw:
        return None
    if raw in _FORBIDDEN_CHAINS:
        return None
    if _CHAIN.match(raw):
        return raw
    return None


def coinstats_get(path: str, query: dict[str, str] | None = None, *, timeout: int | None = None) -> Any:
    """HTTPS GET to api.coinstats.app. The API key is never returned."""
    if not allowed_coinstats_path(path):
        raise ValueError("Refusing request to a CoinStats path that is not on the allowlist.")
    qs = urllib.parse.urlencode(query or {})
    url = f"https://{COINSTATS_API_HOST}{path}"
    if qs:
        url = f"{url}?{qs}"
    parsed = urllib.request.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError("Refusing request to a host that is not on the allowlist.")
    request = urllib.request.Request(url, method="GET", headers=_headers())
    wait = timeout if timeout is not None else _TIMEOUT_SECONDS
    try:
        with urllib.request.urlopen(request, timeout=wait) as response:
            raw = response.read(_MAX_BYTES + 1)
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        return {"error": _http_error_message(exc)}
    except urllib.error.URLError:
        return {"error": "Could not reach api.coinstats.app. Try again later."}
    if len(raw) > _MAX_BYTES:
        return {"error": "Response from CoinStats was too large."}
    if status == 401:
        return {"error": _unauthorized_message()}
    if status == 429:
        return {"error": "CoinStats rate-limited this request (429). Check credit usage."}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"error": "CoinStats returned a non-JSON body."}


def _unauthorized_message() -> str:
    return (
        "COINSTATS_API_KEY was rejected or missing (401). "
        f"Create a key at {DASHBOARD_URL} or use the Cursor OAuth MCP."
    )


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    if exc.code == 401:
        return _unauthorized_message()
    if exc.code == 404:
        return "CoinStats returned 404. Check the coin id, portfolio id, or wallet address."
    if exc.code == 429:
        return "CoinStats rate-limited this request (429). Check credit usage."
    return f"HTTP {exc.code} from api.coinstats.app"


def _format_usd(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    if abs(value) >= 1:
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _format_pct(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _format_coin_payload(payload: dict[str, Any]) -> str:
    coin_id = str(payload.get("id") or payload.get("slug") or "?")
    name = str(payload.get("name") or coin_id)
    symbol = str(payload.get("symbol") or "?")
    lines = [
        f"CoinStats {name} ({symbol}, id {coin_id}):",
        f"- price: ${_format_usd(payload.get('price'))}",
        f"- 1h {_format_pct(payload.get('priceChange1h'))}  "
        f"24h {_format_pct(payload.get('priceChange1d'))}  "
        f"7d {_format_pct(payload.get('priceChange1w'))}",
        f"- market cap: ${_format_usd(payload.get('marketCap'))}",
        f"- volume 24h: ${_format_usd(payload.get('volume'))}",
        f"- rank: {payload.get('rank', 'n/a')}",
    ]
    if isinstance(payload.get("riskScore"), (int, float)):
        lines.append(f"- riskScore: {payload['riskScore']}")
    lines.append("Read-only. This agent will not trade or edit a portfolio.")
    return "\n".join(lines)


def _format_markets_payload(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "CoinStats global market:",
            f"- market cap: ${_format_usd(payload.get('marketCap'))}  "
            f"24h {_format_pct(payload.get('marketCapChange'))}",
            f"- volume 24h: ${_format_usd(payload.get('volume'))}  "
            f"24h {_format_pct(payload.get('volumeChange'))}",
            f"- BTC dominance: {_format_usd(payload.get('btcDominance'))}%  "
            f"24h {_format_pct(payload.get('btcDominanceChange'))}",
            "Read-only. This agent will not trade or edit a portfolio.",
        ]
    )


def _format_portfolio_list(payload: dict[str, Any]) -> str:
    rows = payload.get("result")
    if not isinstance(rows, list):
        return "CoinStats portfolio list returned an unexpected payload."
    if not rows:
        return "No CoinStats portfolios on this API key (watchlists are excluded)."
    lines = [f"CoinStats portfolios ({len(rows)}; watchlists excluded):"]
    for item in rows[:20]:
        if not isinstance(item, dict):
            continue
        pid = item.get("portfolioId") or "?"
        name = item.get("portfolioName") or "unnamed"
        kind = item.get("portfolioType") or "?"
        lines.append(f"- {name}  id {pid}  type {kind}")
    if len(rows) > 20:
        lines.append(f"... {len(rows) - 20} more omitted.")
    lines.append("Pass an id to `coinstats portfolio <id>` for coins + PnL.")
    lines.append("Read-only. This agent will not add, connect, sync, or delete.")
    return "\n".join(lines)


def _nested_usd(container: Any, *keys: str) -> Any:
    current = container
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _format_portfolio_coins(payload: dict[str, Any], portfolio_id: str) -> str:
    rows = payload.get("result")
    if not isinstance(rows, list):
        return "CoinStats portfolio coins returned an unexpected payload."
    label = portfolio_id or "all portfolios"
    if not rows:
        return f"No coins in CoinStats portfolio {label}."
    lines = [f"CoinStats portfolio coins ({label}, showing {min(len(rows), _MAX_PORTFOLIO_ROWS)} of {len(rows)}):"]
    for item in rows[:_MAX_PORTFOLIO_ROWS]:
        if not isinstance(item, dict):
            continue
        coin = item.get("coin") if isinstance(item.get("coin"), dict) else {}
        symbol = str(coin.get("symbol") or item.get("symbol") or "?")
        name = str(coin.get("name") or symbol)
        count = item.get("count")
        price = _nested_usd(item.get("price"), "USD")
        pnl = _nested_usd(item.get("profit"), "unrealized", "USD")
        pnl_pct = _nested_usd(item.get("profitPercent"), "unrealized", "USD")
        extra = []
        if isinstance(count, (int, float)):
            extra.append(f"qty {count:g}")
        if isinstance(price, (int, float)):
            extra.append(f"${_format_usd(price)}")
        if isinstance(pnl, (int, float)):
            extra.append(f"uPnL ${_format_usd(pnl)}")
        if isinstance(pnl_pct, (int, float)):
            extra.append(_format_pct(pnl_pct))
        suffix = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"- {symbol} {name}{suffix}")
    if len(rows) > _MAX_PORTFOLIO_ROWS:
        lines.append(f"... {len(rows) - _MAX_PORTFOLIO_ROWS} more omitted.")
    lines.append("Read-only. This agent will not add, connect, sync, or delete.")
    return "\n".join(lines)


def _format_wallet_payload(payload: Any, address: str, chain: str) -> str:
    if not isinstance(payload, list):
        return "CoinStats wallet balance returned an unexpected payload."
    if not payload:
        return f"No CoinStats balances for {address} on {chain}."
    lines = [
        f"CoinStats wallet {address} ({chain}, showing "
        f"{min(len(payload), _MAX_WALLET_ROWS)} of {len(payload)}):"
    ]
    for item in payload[:_MAX_WALLET_ROWS]:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "?")
        name = str(item.get("name") or symbol)
        amount = item.get("amount")
        price = item.get("price")
        usd = None
        if isinstance(amount, (int, float)) and isinstance(price, (int, float)):
            usd = amount * price
        bits = []
        if isinstance(amount, (int, float)):
            bits.append(f"{amount:g}")
        if usd is not None:
            bits.append(f"${_format_usd(usd)}")
        if isinstance(item.get("pCh24h"), (int, float)):
            bits.append(f"24h {_format_pct(item['pCh24h'])}")
        suffix = f" ({', '.join(bits)})" if bits else ""
        lines.append(f"- {symbol} {name}{suffix}")
    if len(payload) > _MAX_WALLET_ROWS:
        lines.append(f"... {len(payload) - _MAX_WALLET_ROWS} more omitted.")
    lines.append("Read-only public lookup. This agent will not send or sign.")
    return "\n".join(lines)


@tool
def coinstats_overview() -> str:
    """Explain CoinStats MCP and read-only REST tools.

    Does not attach write tools or complete OAuth.
    """
    return _overview_text()


@tool
def coinstats_coin(coin: str) -> str:
    """USD price and market data for a CoinStats coin id or known symbol.

    Examples: bitcoin, BTC, ethereum, SOL. Needs COINSTATS_API_KEY.
    Read-only; does not trade.
    """
    raw = (coin or "").strip()
    if not raw:
        return "Provide a coin id or symbol: coinstats coin bitcoin"
    if _secret_query(raw):
        return "Do not paste seed phrases, private keys, API keys, or share tokens."
    coin_id = resolve_coin_id(raw)
    if not coin_id:
        return (
            "Provide a CoinStats coin id or known symbol "
            "(bitcoin, BTC, ethereum, ETH, solana, SOL, USDC, USDT)."
        )
    if not coinstats_api_key():
        return _missing_key_message("Coin price")
    payload = coinstats_get(_coin_path(coin_id), {"currency": "USD"})
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    if not isinstance(payload, dict):
        return "CoinStats coin lookup returned an unexpected payload."
    return _format_coin_payload(payload)


@tool
def coinstats_markets() -> str:
    """Global crypto market cap, volume, and BTC dominance from CoinStats.

    Needs COINSTATS_API_KEY. Read-only.
    """
    if not coinstats_api_key():
        return _missing_key_message("Global market data")
    payload = coinstats_get("/v1/markets")
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    if not isinstance(payload, dict):
        return "CoinStats markets returned an unexpected payload."
    return _format_markets_payload(payload)


@tool
def coinstats_portfolio_list() -> str:
    """List CoinStats portfolios for the API key (watchlists excluded).

    Needs COINSTATS_API_KEY. Read-only; does not create or delete.
    """
    if not coinstats_api_key():
        return _missing_key_message("Portfolio list")
    payload = coinstats_get("/v1/portfolio/list")
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    if not isinstance(payload, dict):
        return "CoinStats portfolio list returned an unexpected payload."
    return _format_portfolio_list(payload)


@tool
def coinstats_portfolio(portfolio_id: str = "") -> str:
    """Holdings and unrealized PnL for one CoinStats portfolio, or all.

    Pass a portfolioId from coinstats_portfolio_list, or omit / 'all' to
    aggregate. Needs COINSTATS_API_KEY. Read-only.
    """
    raw = (portfolio_id or "").strip()
    if _secret_query(raw):
        return "Do not paste seed phrases, private keys, API keys, or share tokens."
    if raw and raw.lower() not in {"all", "aggregate", "*", "coins"}:
        resolved = resolve_portfolio_id(raw)
        if resolved is None:
            return "Provide a portfolioId from `coinstats portfolio list`, or omit it to aggregate all."
        raw = resolved
    else:
        raw = ""
    if not coinstats_api_key():
        return _missing_key_message("Portfolio coins")
    query: dict[str, str] = {"limit": "20", "page": "1"}
    if raw:
        query["portfolioId"] = raw
    payload = coinstats_get("/v1/portfolio/coins", query)
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    if not isinstance(payload, dict):
        return "CoinStats portfolio coins returned an unexpected payload."
    return _format_portfolio_coins(payload, raw)


@tool
def coinstats_wallet(address: str, blockchain: str = "") -> str:
    """Public CoinStats balances for one wallet address on one chain.

    Pass a Bitcoin, EVM, or other supported address plus an optional
    chain (bitcoin, ethereum, solana). Does not query every chain.
    Needs COINSTATS_API_KEY. Read-only; does not send.
    """
    raw = (address or "").strip()
    if not raw:
        return "Provide a wallet address: coinstats wallet <address> [bitcoin|ethereum|solana]"
    if _secret_query(raw) or _secret_query(blockchain or ""):
        return "Do not paste seed phrases, private keys, API keys, or share tokens."
    if classify_payment_id(raw) == "secret":
        return "Do not paste seed phrases, private keys, API keys, or share tokens."
    if len(raw) < 8 or len(raw) > 200 or " " in raw:
        return "That does not look like a single wallet address."
    requested_chain = (blockchain or "").strip().lower()
    if requested_chain in _FORBIDDEN_CHAINS:
        return (
            "This agent will not query `all` / `forceall` (those burn credits). "
            "Pass one chain such as bitcoin, ethereum, or solana."
        )
    chain = resolve_wallet_chain(blockchain) or _default_wallet_chain(raw)
    if not chain:
        return (
            "Provide one chain (bitcoin, ethereum, solana, …). "
            "This agent will not query `all` / `forceall` (those burn credits)."
        )
    if not coinstats_api_key():
        return _missing_key_message("Wallet balance")
    payload = coinstats_get(
        "/v1/wallet/balance",
        {"address": raw, "blockchain": chain},
        timeout=_WALLET_TIMEOUT_SECONDS,
    )
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    return _format_wallet_payload(payload, raw, chain)


@tool
def coinstats_status() -> str:
    """Report whether COINSTATS_API_KEY is set. Never prints the key."""
    if coinstats_api_key():
        key_state = "set (not printed; used as X-API-KEY for api.coinstats.app)"
    else:
        key_state = f"unset — REST tools stay off until you export a key from {DASHBOARD_URL}"
    return (
        "CoinStats status:\n"
        f"- COINSTATS_API_KEY: {key_state}\n"
        f"- Cursor MCP: {MCP_URL} (OAuth; already in .cursor/mcp.json)\n"
        "- Runtime hosted MCP: not attached (write tools: add / connect / "
        "sync / delete portfolio)\n"
        f"- Stdio fallback (not attached): {STDIO_COMMAND}\n"
        "Read-only here. This agent will not mutate a CoinStats portfolio."
    )
