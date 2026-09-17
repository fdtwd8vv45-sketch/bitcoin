"""Read-only Jupiter Price / Tokens lookups and CLI status.

Jupiter APIs are REST/JSON at api.jup.ag. Keyless access works at 0.5 RPS;
an optional JUPITER_API_KEY raises the limit via the x-api-key header.

This module never swaps, places orders, signs, or runs the Jupiter CLI
except `jup --version`. Trading stays in the official CLI / Trading MCP.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp_client.settings import jupiter_api_key
from optional_tool import tool

JUPITER_API_HOST = "api.jup.ag"
DOCS_URL = "https://developers.jup.ag/docs/ai"
LLMS_TXT_URL = "https://dev.jup.ag/docs/llms.txt"
SKILLS_URL = "https://developers.jup.ag/docs/ai/skills"
CLI_DOCS_URL = "https://developers.jup.ag/docs/ai/cli"
DOCS_MCP_URL = "https://developers.jup.ag/docs/mcp"
TRADING_MCP_URL = "https://mcp.jup.ag"
PORTAL_URL = "https://developers.jup.ag/portal"
PRICE_DOCS_URL = "https://developers.jup.ag/docs/price"
TOKENS_DOCS_URL = "https://developers.jup.ag/docs/tokens"
INSTALL_COMMAND = "npm i -g @jup-ag/cli"
SKILLS_COMMAND = 'npx skills add jup-ag/agent-skills --skill "integrating-jupiter"'
_ALLOWED_HOSTS = {JUPITER_API_HOST}
_ALLOWED_PATHS = ("/price/v3", "/tokens/v2/search")
_TIMEOUT_SECONDS = 8
_MAX_BYTES = 256_000
_MAX_SEARCH_RESULTS = 8
_MAX_PRICE_IDS = 50
_CLI_TIMEOUT_SECONDS = 8
_MAX_CLI_BYTES = 8_000
_STOPWORDS = {
    "a",
    "about",
    "ai",
    "an",
    "and",
    "api",
    "check",
    "cli",
    "current",
    "do",
    "docs",
    "for",
    "from",
    "get",
    "give",
    "how",
    "i",
    "info",
    "information",
    "is",
    "jupiter",
    "live",
    "look",
    "mcp",
    "me",
    "mint",
    "mints",
    "now",
    "of",
    "on",
    "or",
    "please",
    "price",
    "quote",
    "search",
    "show",
    "status",
    "swap",
    "symbol",
    "tell",
    "the",
    "to",
    "today",
    "token",
    "tokens",
    "up",
    "usd",
    "using",
    "via",
    "vs",
    "we",
    "what",
    "with",
}
_BASE58_MINT = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_SYMBOL = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,15}$")

# Official mints so "price JUP" does not pick up ticker copycats from search.
KNOWN_MINTS: dict[str, str] = {
    "sol": "So11111111111111111111111111111111111111112",
    "wsol": "So11111111111111111111111111111111111111112",
    "usdc": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "usdt": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "jup": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "jupusd": "JuprjznTrTSp2UFa3ZBUFgwdAmtZCq4MQCwysN55USD",
    "jupsol": "jupSoLaHXQiZZTSfEWMTRRgpnyFm8f6sZdosWBjx93v",
    "jlp": "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4",
}

_MINT_TO_SYMBOL = {
    mint: symbol.upper() if symbol != "wsol" else "SOL"
    for symbol, mint in KNOWN_MINTS.items()
    if symbol != "wsol"
}


def _overview_text() -> str:
    return (
        "Jupiter is Solana DeFi infrastructure. APIs are REST/JSON, need no "
        "RPC node, and return clean responses agents can parse.\n"
        "\n"
        "Read the docs:\n"
        f"- llms.txt index: {LLMS_TXT_URL}\n"
        f"- Skills (integrating-jupiter): {SKILLS_COMMAND}\n"
        f"  {SKILLS_URL}\n"
        f"- Docs MCP (read-only): {DOCS_MCP_URL}\n"
        "  Cursor is already wired in .cursor/mcp.json as jupiter-docs.\n"
        "  Runtime: set JUPITER_DOCS_MCP=1 (or JUPITER_API_KEY).\n"
        "\n"
        "Execute operations (not through this agent):\n"
        f"- CLI: {INSTALL_COMMAND}  then  jup --help\n"
        f"  {CLI_DOCS_URL}\n"
        f"- Trading MCP: {TRADING_MCP_URL}  (swap / orders / lend). "
        "BitcoinAgent does not attach it.\n"
        "\n"
        "This agent is read-only: overview, USD prices, token search, and "
        "`jup --version`. It does not swap, place orders, lend, or sign.\n"
        "\n"
        "Price and Tokens work keyless at 0.5 RPS. For higher limits, create "
        f"a key at {PORTAL_URL} and export JUPITER_API_KEY (sent as x-api-key, "
        "never logged).\n"
        "\n"
        "Known symbols for price: SOL, USDC, USDT, JUP, JupUSD, JupSOL, JLP "
        "(or a mint address).\n"
        "Local:\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter price SOL,JUP\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter token JUP\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter status\n"
        f"Docs: {DOCS_URL}  |  Price: {PRICE_DOCS_URL}  |  Tokens: {TOKENS_DOCS_URL}"
    )


def _secret_query(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("seed", "xprv", "private", "secret key", "api key"))


def split_query_tokens(text: str) -> list[str]:
    """Split a user query into symbol / mint tokens."""
    cleaned = (text or "").replace(",", " ")
    return [part for part in cleaned.split() if part]


def resolve_price_id(token: str) -> str | None:
    """Map a symbol or mint to a Price API id, or None if unusable."""
    raw = token.strip()
    if not raw or _secret_query(raw):
        return None
    alias = KNOWN_MINTS.get(raw.lower())
    if alias:
        return alias
    if _BASE58_MINT.match(raw):
        return raw
    return None


def resolve_price_ids(text: str) -> tuple[list[str], list[str]]:
    """Return (mint ids, leftover tokens that still need search)."""
    ids: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for token in split_query_tokens(text):
        mint = resolve_price_id(token)
        if mint:
            if mint not in seen:
                ids.append(mint)
                seen.add(mint)
            continue
        if token.lower() in _STOPWORDS:
            continue
        if _SYMBOL.match(token):
            unknown.append(token)
    return ids, unknown


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": "BitcoinAgent/1.0"}
    key = jupiter_api_key()
    if key:
        headers["x-api-key"] = key
    return headers


def jupiter_get(path: str, query: dict[str, str]) -> Any:
    """HTTPS GET to api.jup.ag. The API key is never returned to the caller."""
    if path not in _ALLOWED_PATHS:
        raise ValueError("Refusing request to a Jupiter path that is not on the allowlist.")
    qs = urllib.parse.urlencode(query)
    url = f"https://{JUPITER_API_HOST}{path}?{qs}"
    parsed = urllib.request.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError("Refusing request to a host that is not on the allowlist.")
    request = urllib.request.Request(url, method="GET", headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            raw = response.read(_MAX_BYTES + 1)
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        return {"error": _http_error_message(exc)}
    except urllib.error.URLError:
        return {"error": "Could not reach api.jup.ag. Try again later."}
    if len(raw) > _MAX_BYTES:
        return {"error": "Response from Jupiter was too large."}
    if status == 401:
        return {"error": "JUPITER_API_KEY was rejected (401). Unset it to run keyless, or replace it."}
    if status == 429:
        return {
            "error": "Jupiter rate-limited this request (429). Keyless is 0.5 RPS; "
            f"a Portal key raises the limit ({PORTAL_URL})."
        }
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"error": "Jupiter returned a non-JSON body."}


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    if exc.code == 401:
        return "JUPITER_API_KEY was rejected (401). Unset it to run keyless, or replace it."
    if exc.code == 429:
        return (
            "Jupiter rate-limited this request (429). Keyless is 0.5 RPS; "
            f"a Portal key raises the limit ({PORTAL_URL})."
        )
    return f"HTTP {exc.code} from api.jup.ag"


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


def _format_price_payload(payload: dict[str, Any], requested: list[str]) -> str:
    lines: list[str] = ["Jupiter Price API v3 (USD, last reliable swap):"]
    for mint in requested:
        entry = payload.get(mint)
        label = _MINT_TO_SYMBOL.get(mint, mint)
        if not isinstance(entry, dict):
            lines.append(f"- {label} ({mint}): no reliable price (omitted by Jupiter heuristics)")
            continue
        usd = _format_usd(entry.get("usdPrice"))
        change = _format_pct(entry.get("priceChange24h"))
        decimals = entry.get("decimals")
        block = entry.get("blockId")
        extra = []
        if isinstance(decimals, int):
            extra.append(f"decimals {decimals}")
        if isinstance(block, int):
            extra.append(f"block {block}")
        suffix = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"- {label} ({mint}): ${usd}  24h {change}{suffix}")
    lines.append("Read-only. This agent will not swap or sign.")
    return "\n".join(lines)


def _pick_search_mints(tokens: list[dict[str, Any]], limit: int = 3) -> list[str]:
    verified = [item["id"] for item in tokens if isinstance(item, dict) and item.get("isVerified") and item.get("id")]
    chosen = verified[:limit]
    if chosen:
        return chosen
    return [item["id"] for item in tokens[:limit] if isinstance(item, dict) and item.get("id")]


def _search_tokens_payload(query: str) -> Any:
    return jupiter_get("/tokens/v2/search", {"query": query})


def _format_token(item: dict[str, Any]) -> str:
    mint = str(item.get("id") or "")
    name = str(item.get("name") or "unknown")
    symbol = str(item.get("symbol") or "?")
    verified = item.get("isVerified")
    score = item.get("organicScore")
    label = item.get("organicScoreLabel")
    usd = item.get("usdPrice")
    mcap = item.get("mcap")
    holders = item.get("holderCount")
    tags = item.get("tags") or []
    audit = item.get("audit") if isinstance(item.get("audit"), dict) else {}
    flags: list[str] = []
    if verified is True:
        flags.append("verified")
    elif verified is False:
        flags.append("unverified")
    if audit.get("isSus"):
        flags.append("suspicious")
    if isinstance(score, (int, float)):
        score_text = f"{score:.1f}"
        if isinstance(label, str) and label:
            score_text += f" {label}"
        flags.append(f"organic {score_text}")
    lines = [f"- {symbol} ({name})", f"  mint: {mint}"]
    if flags:
        lines.append("  " + ", ".join(flags))
    if isinstance(usd, (int, float)):
        lines.append(f"  usdPrice: ${_format_usd(usd)}")
    if isinstance(mcap, (int, float)):
        lines.append(f"  mcap: ${_format_usd(mcap)}")
    if isinstance(holders, int):
        lines.append(f"  holders: {holders:,}")
    if isinstance(tags, list) and tags:
        shown = [str(tag) for tag in tags[:8]]
        lines.append("  tags: " + ", ".join(shown))
    return "\n".join(lines)


def _format_search_payload(payload: Any, query: str) -> str:
    if not isinstance(payload, list):
        return "Jupiter Tokens search returned an unexpected payload."
    if not payload:
        return f"No Jupiter tokens matched {query!r}."
    shown = payload[:_MAX_SEARCH_RESULTS]
    lines = [
        f"Jupiter Tokens API v2 search for {query!r} "
        f"(showing {len(shown)} of {len(payload)}; prefer verified + high organic score):"
    ]
    for item in shown:
        if isinstance(item, dict):
            lines.append(_format_token(item))
    if len(payload) > _MAX_SEARCH_RESULTS:
        lines.append(f"... {len(payload) - _MAX_SEARCH_RESULTS} more hits omitted.")
    lines.append(
        "Ticker collisions are common. Check mint + isVerified before using a result. "
        "Read-only. This agent will not swap or sign."
    )
    return "\n".join(lines)


@tool
def jupiter_overview() -> str:
    """Explain Jupiter APIs and AI tools (llms.txt, skills, docs MCP, CLI).

    Read-only. Does not swap, place orders, or sign.
    """
    return _overview_text()


@tool
def jupiter_price(ids: str) -> str:
    """USD prices from Jupiter Price API v3 for Solana mints or known symbols.

    Pass comma-separated symbols (SOL, USDC, USDT, JUP, JupUSD, JupSOL, JLP)
    or mint addresses, up to 50. Read-only; does not swap.
    """
    raw = (ids or "").strip()
    if not raw:
        return (
            "Provide symbols or mint addresses: jupiter price SOL,JUP\n"
            "Known symbols: SOL, USDC, USDT, JUP, JupUSD, JupSOL, JLP."
        )
    if _secret_query(raw):
        return "Do not paste seed phrases, private keys, or API keys."
    mints, unknown = resolve_price_ids(raw)
    if unknown:
        # Resolve leftover symbols via search so "BONK" still works, preferring verified.
        search = _search_tokens_payload(",".join(unknown[:10]))
        if isinstance(search, dict) and search.get("error"):
            return str(search["error"])
        if isinstance(search, list):
            for mint in _pick_search_mints(search, limit=len(unknown)):
                if mint not in mints:
                    mints.append(mint)
        elif unknown and not mints:
            leftover = ", ".join(unknown)
            return (
                f"Could not resolve {leftover!r} to a mint. "
                "Use a known symbol (SOL, USDC, JUP, …) or a mint address."
            )
    if not mints:
        return (
            "Provide symbols or mint addresses: jupiter price SOL,JUP\n"
            "Known symbols: SOL, USDC, USDT, JUP, JupUSD, JupSOL, JLP."
        )
    if len(mints) > _MAX_PRICE_IDS:
        return f"Price API accepts at most {_MAX_PRICE_IDS} ids per request."
    payload = jupiter_get("/price/v3", {"ids": ",".join(mints)})
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    if not isinstance(payload, dict):
        return "Jupiter Price API returned an unexpected payload."
    return _format_price_payload(payload, mints)


@tool
def jupiter_token_search(query: str) -> str:
    """Search Solana tokens on Jupiter Tokens API v2 by name, symbol, or mint.

    Returns metadata, verification, and organic score. Read-only; does not swap.
    """
    raw = (query or "").strip()
    if not raw:
        return "Provide a symbol, name, or mint: jupiter token JUP"
    if _secret_query(raw):
        return "Do not paste seed phrases, private keys, or API keys."
    if len(raw) > 400:
        return "Token search query is too long."
    payload = _search_tokens_payload(raw)
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    return _format_search_payload(payload, raw)


def jup_cli_path() -> str | None:
    return shutil.which("jup")


def run_jup_version(cli_path: str | None = None) -> dict[str, Any]:
    """Run `jup --version` only. Never keys / swap / sign."""
    binary = cli_path or jup_cli_path()
    if not binary:
        return {"error": "jup CLI is not on PATH"}
    try:
        completed = subprocess.run(
            [binary, "--version"],
            check=False,
            capture_output=True,
            timeout=_CLI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"error": "jup --version timed out"}
    except OSError:
        return {"error": "Could not execute jup"}
    raw = completed.stdout or completed.stderr
    if len(raw) > _MAX_CLI_BYTES:
        return {"error": "jup --version returned too much data"}
    try:
        decoded = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return {"error": "jup --version returned a non-text body"}
    snippet = decoded.splitlines()[0][:200] if decoded else "empty output"
    if completed.returncode != 0:
        return {"error": f"jup --version failed: {snippet}"}
    return {"version": snippet}


@tool
def jupiter_cli_status() -> str:
    """Check whether the official Jupiter CLI (`jup`) is on PATH.

    Read-only. Runs `jup --version` only. Does not add keys, swap, or sign.
    """
    binary = jup_cli_path()
    if not binary:
        return (
            "jup CLI: not found on PATH.\n"
            f"Install: {INSTALL_COMMAND}\n"
            f"Then: {CLI_DOCS_URL}\n"
            "BitcoinAgent will not run swap, keys, or sign commands. Use the "
            "official CLI on a machine you control if you need to trade."
        )
    payload = run_jup_version(binary)
    if payload.get("error"):
        return (
            f"jup CLI: {binary}\n"
            f"{payload['error']}\n"
            "Status is read-only. BitcoinAgent will not run swap, keys, or sign."
        )
    return (
        f"jup CLI: {binary}\n"
        f"Version: {payload.get('version')}\n"
        "BitcoinAgent only checks the version. Swap, keys, and sign stay in "
        "the official CLI — not here."
    )
