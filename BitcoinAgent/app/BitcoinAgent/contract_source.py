"""Retrieve verified EVM contract source from the Etherscan API.

Read-only HTTPS GET to api.etherscan.io. Requires ETHERSCAN_API_KEY.
Never logs the key, never executes retrieved source, and never asks for
the key in chat.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp_client.settings import etherscan_api_key
from optional_tool import tool

ETHERSCAN_API_HOST = "api.etherscan.io"
ETHERSCAN_API_PATH = "/v2/api"
DOCS_URL = "https://docs.etherscan.io/api-reference/endpoint/getsourcecode"
KEY_URL = "https://etherscan.io/apidashboard"
_ALLOWED_HOSTS = {ETHERSCAN_API_HOST}
_ETH_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_CHAIN_ID = re.compile(r"^[0-9]{1,18}$")
_TIMEOUT_SECONDS = 8
_MAX_BYTES = 2_000_000
_MAX_SOURCE_CHARS = 16_000
_MAX_ABI_CHARS = 8_000
_MISSING_KEY = (
    "Set ETHERSCAN_API_KEY to retrieve verified contract source from the "
    f"Etherscan API ({KEY_URL}). Create a free key, export it in the environment, "
    "then retry. This tool is read-only and counts against your Etherscan quota."
)

# Common names from Etherscan docs / CLI; numeric chain IDs always work.
CHAIN_ALIASES = {
    "ethereum": "1",
    "eth": "1",
    "mainnet": "1",
    "arbitrum": "42161",
    "arb": "42161",
    "optimism": "10",
    "op": "10",
    "base": "8453",
    "polygon": "137",
    "matic": "137",
    "bsc": "56",
    "bnb": "56",
    "avalanche": "43114",
    "avax": "43114",
    "sepolia": "11155111",
}


def normalize_chain_id(chain: str | None) -> str | None:
    """Return a numeric chain id, or None if the value is not usable."""
    text = (chain or "1").strip().lower()
    if not text:
        text = "1"
    text = CHAIN_ALIASES.get(text, text)
    if text.startswith("chainid="):
        text = text.split("=", 1)[1].strip()
    if not _CHAIN_ID.match(text):
        return None
    return text.lstrip("0") or "0"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n... [truncated, {omitted} characters omitted]"


def _get_json(url: str) -> Any:
    parsed = urllib.request.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError("Refusing request to a host that is not on the allowlist.")
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "BitcoinAgent/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            raw = response.read(_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code} from Etherscan"}
    except urllib.error.URLError:
        return {"error": "Could not reach api.etherscan.io. Try again later."}
    if len(raw) > _MAX_BYTES:
        return {"error": "Response from Etherscan was too large."}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"error": "Etherscan returned a non-JSON body."}


def etherscan_get(params: dict[str, str]) -> Any:
    """GET /v2/api with an API key. The key is never returned to the caller."""
    key = etherscan_api_key()
    if not key:
        return {"error": _MISSING_KEY}
    query = {**params, "apikey": key}
    url = f"https://{ETHERSCAN_API_HOST}{ETHERSCAN_API_PATH}?{urllib.parse.urlencode(query)}"
    return _get_json(url)


def parse_source_files(source_code: str) -> list[tuple[str, str]]:
    """Split Etherscan SourceCode into (filename, content) pairs.

    Single-file verifications are a Solidity/Vyper string. Multi-file
    verifications are a Standard JSON input, sometimes wrapped in extra braces.
    """
    text = (source_code or "").strip()
    if not text:
        return []

    candidates = [text]
    if text.startswith("{{") and text.endswith("}}"):
        candidates.insert(0, text[1:-1])

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        sources = payload.get("sources")
        if isinstance(sources, dict) and sources:
            files: list[tuple[str, str]] = []
            for name, body in sources.items():
                if isinstance(body, dict):
                    content = str(body.get("content") or "")
                elif isinstance(body, str):
                    content = body
                else:
                    content = ""
                files.append((str(name), content.replace("\r\n", "\n")))
            return files
        # Older multi-file shape: { "Foo.sol": { "content": "..." }, ... }
        if all(isinstance(v, dict) and "content" in v for v in payload.values()):
            return [
                (str(name), str(body.get("content") or "").replace("\r\n", "\n"))
                for name, body in payload.items()
            ]

    return [("source.sol", source_code.replace("\r\n", "\n"))]


def abi_summary(abi_text: str) -> str:
    if not abi_text or abi_text.startswith("Contract source code not verified"):
        return abi_text or ""
    try:
        abi = json.loads(abi_text)
    except json.JSONDecodeError:
        return _truncate(abi_text, 500)
    if not isinstance(abi, list):
        return _truncate(abi_text, 500)
    lines: list[str] = []
    for item in abi:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "function")
        name = str(item.get("name") or kind)
        if kind == "constructor":
            lines.append("constructor")
            continue
        if kind in {"fallback", "receive"}:
            lines.append(kind)
            continue
        mut = str(item.get("stateMutability") or "").strip()
        extra = f" ({mut})" if mut else ""
        lines.append(f"{kind} {name}{extra}")
    return "\n".join(lines) if lines else "(empty ABI)"


def _is_unverified(entry: dict[str, Any]) -> bool:
    source = str(entry.get("SourceCode") or "").strip()
    abi = str(entry.get("ABI") or "")
    return not source and "not verified" in abi.lower()


def format_contract_result(address: str, chain_id: str, entry: dict[str, Any]) -> str:
    source = str(entry.get("SourceCode") or "")
    abi = str(entry.get("ABI") or "")
    name = str(entry.get("ContractName") or "").strip() or "(unknown)"
    proxy = str(entry.get("Proxy") or "0")
    implementation = str(entry.get("Implementation") or "").strip()
    main_file = str(entry.get("ContractFileName") or "").strip()
    similar = str(entry.get("SimilarMatch") or "").strip()

    lines = [
        f"Contract: {name}",
        f"Address: {address}",
        f"Chain ID: {chain_id}",
        f"Docs: {DOCS_URL}",
    ]
    if _is_unverified(entry):
        lines.extend(
            [
                "Verified: no",
                "",
                "This address has no verified source on Etherscan. The call succeeded; "
                "SourceCode is empty and ABI is 'Contract source code not verified'. "
                "Do not infer behavior from the name or bytecode.",
            ]
        )
        if similar:
            lines.append(f"Similar verified match: {similar}")
        return "\n".join(lines)

    lines.extend(
        [
            "Verified: yes",
            f"Compiler: {entry.get('CompilerType') or 'unknown'} {entry.get('CompilerVersion') or ''}".rstrip(),
            f"Optimization: {entry.get('OptimizationUsed') or '?'} "
            f"(runs: {entry.get('Runs') or '?'})",
            f"EVM: {entry.get('EVMVersion') or 'Default'}",
            f"License: {entry.get('LicenseType') or 'None'}",
            f"Proxy: {proxy}",
        ]
    )
    if implementation:
        lines.append(f"Implementation: {implementation}")
        if proxy == "1":
            lines.append(
                "This address is a proxy. The source below is the proxy; "
                "call this tool again on the implementation address for the logic."
            )
    if main_file:
        lines.append(f"Main file: {main_file}")
    ctor = str(entry.get("ConstructorArguments") or "").strip()
    if ctor:
        lines.append(f"Constructor arguments: {_truncate(ctor, 240)}")
    library = str(entry.get("Library") or "").strip()
    if library:
        lines.append(f"Library: {library}")
    swarm = str(entry.get("SwarmSource") or "").strip()
    if swarm:
        lines.append(f"Swarm: {swarm}")
    if similar:
        lines.append(f"Similar verified match: {similar}")

    files = parse_source_files(source)
    if files:
        lines.append("")
        lines.append(f"Source files ({len(files)}):")
        for filename, content in files:
            lines.append(f"  - {filename} ({len(content)} chars)")

        chosen_name, chosen_body = files[0]
        if main_file:
            for filename, content in files:
                if filename == main_file or filename.endswith(main_file):
                    chosen_name, chosen_body = filename, content
                    break
        lines.append("")
        lines.append(f"## {chosen_name}")
        lines.append(_truncate(chosen_body, _MAX_SOURCE_CHARS))
        leftover = [filename for filename, _content in files if filename != chosen_name]
        if leftover:
            lines.append("")
            lines.append("Other files not printed: " + ", ".join(leftover))

    summary = abi_summary(abi)
    if summary:
        lines.append("")
        lines.append("ABI entries:")
        lines.append(summary)
    if abi and not abi.startswith("Contract source code not verified"):
        lines.append("")
        lines.append("ABI JSON:")
        lines.append(_truncate(abi, _MAX_ABI_CHARS))

    lines.append("")
    lines.append(
        "Read-only metadata from Etherscan. Do not run this source, and do not "
        "treat a name, comment, or ABI entry as proof of behavior without reading "
        "the implementation."
    )
    return "\n".join(lines)


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


@tool
def lookup_contract_source(address: str, chainid: str = "1") -> str:
    """Retrieve verified source, ABI, and compiler settings for an EVM contract.

    Uses Etherscan API v2 action getsourcecode. Requires ETHERSCAN_API_KEY.
    Pass chainid as a number (1 for Ethereum, 42161 for Arbitrum) or a name
    such as ethereum, arbitrum, base. Read-only; never execute the source.
    """
    address = address.strip()
    if not address:
        return "Provide a contract address such as 0xBB9bc244D798123fDe783fCc1C72d3Bb8C189413."
    lowered = address.lower()
    if any(token in lowered for token in ("seed", "xprv", "private", "mnemonic")):
        return "Do not paste seed phrases or private keys."
    if not _ETH_ADDRESS.match(address):
        return "Address must be a 20-byte EVM address (0x followed by 40 hex characters)."

    chain_id = normalize_chain_id(chainid)
    if chain_id is None:
        return (
            "chainid must be a numeric Etherscan chain ID (for example 1) or a "
            "known name such as ethereum, arbitrum, or base. "
            "See https://docs.etherscan.io/supported-chains."
        )

    if not etherscan_api_key():
        return _MISSING_KEY

    payload = etherscan_get(
        {
            "chainid": chain_id,
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        }
    )
    error = _api_error(payload)
    if error:
        return error

    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, list) or not result:
        return "Etherscan returned no contract records for that address."
    entry = result[0]
    if not isinstance(entry, dict):
        return "Etherscan returned a malformed contract record."
    return format_contract_result(address, chain_id, entry)
