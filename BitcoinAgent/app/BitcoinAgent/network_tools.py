"""Public Bitcoin network lookups (no credentials; read-only HTTP GET).

mempool.space is a public REST API with no auth. AgentCore OpenAPI gateway
targets require an API key, so these calls stay in agent code and only hit
an allowlisted host. Do not use this module for wallet or private-key data.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from optional_tool import tool

_ALLOWED_HOSTS = {"mempool.space"}
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_TIMEOUT_SECONDS = 8
_MAX_BYTES = 256_000


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
        return {"error": f"HTTP {exc.code} from mempool.space"}
    except urllib.error.URLError:
        return {"error": "Could not reach mempool.space. Try again later."}
    if len(raw) > _MAX_BYTES:
        return {"error": "Response from mempool.space was too large."}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"error": "mempool.space returned a non-JSON body."}


def _pretty(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


@tool
def recommended_fees() -> str:
    """Return current recommended Bitcoin fee rates from mempool.space (sat/vB)."""
    return _pretty(_get_json("https://mempool.space/api/v1/fees/recommended"))


@tool
def chain_tip_height() -> str:
    """Return the current Bitcoin chain tip height from mempool.space."""
    return _pretty(_get_json("https://mempool.space/api/blocks/tip/height"))


@tool
def difficulty_adjustment() -> str:
    """Return the current Bitcoin difficulty-adjustment estimate from mempool.space."""
    return _pretty(_get_json("https://mempool.space/api/v1/difficulty-adjustment"))


@tool
def lookup_transaction(txid: str) -> str:
    """Look up a confirmed or mempool Bitcoin transaction by 64-character hex txid.

    Public explorer data only. Do not use this for wallet secrets or private keys.
    """
    txid = txid.strip()
    if not _HEX64.match(txid):
        return "txid must be a 64-character hexadecimal transaction id."
    return _pretty(_get_json(f"https://mempool.space/api/tx/{txid}"))
