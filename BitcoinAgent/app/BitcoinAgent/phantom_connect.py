"""Read-only Phantom Connect SDK overview, npm versions, and CLI status.

Source: https://github.com/phantom/phantom-connect-sdk

This module never connects a wallet, signs, sends, logs in, or attaches
the Phantom wallet MCP (@phantom/mcp-server / `phantom --mcp`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp_client.settings import phantom_app_id_set, phantom_docs_mcp_enabled
from optional_tool import tool

GITHUB_URL = "https://github.com/phantom/phantom-connect-sdk"
DOCS_URL = "https://docs.phantom.com"
SDK_OVERVIEW_URL = "https://docs.phantom.com/wallet-sdks-overview"
CONNECT_URL = "https://docs.phantom.com/phantom-connect"
PORTAL_URL = "https://phantom.com/portal"
DOCS_MCP_URL = "https://docs.phantom.com/mcp"
DOCS_MCP_PAGE = "https://docs.phantom.com/resources/mcp-server"
WALLET_MCP_URL = "https://docs.phantom.com/phantom-mcp-server"
CLI_DOCS_URL = "https://docs.phantom.com/phantom-cli"
CLI_INSTALL_COMMAND = "npm install -g @phantom/cli"
REACT_INSTALL = "npm install @phantom/react-sdk"
BROWSER_INSTALL = "npm install @phantom/browser-sdk"
RN_INSTALL = "npm install @phantom/react-native-sdk"
NPM_REGISTRY_HOST = "registry.npmjs.org"
_ALLOWED_HOSTS = {NPM_REGISTRY_HOST}
_TIMEOUT_SECONDS = 8
_MAX_BYTES = 256_000
_CLI_TIMEOUT_SECONDS = 8
_MAX_CLI_BYTES = 8_000

# npm "latest" documents only. Never fetch tarballs or arbitrary packages.
PACKAGES: dict[str, str] = {
    "react": "@phantom/react-sdk",
    "browser": "@phantom/browser-sdk",
    "react-native": "@phantom/react-native-sdk",
    "cli": "@phantom/cli",
}
WALLET_MCP_PACKAGE = "@phantom/mcp-server"
_PACKAGE_ALIASES = {
    "react": "react",
    "react-sdk": "react",
    "@phantom/react-sdk": "react",
    "browser": "browser",
    "browser-sdk": "browser",
    "js": "browser",
    "vanilla": "browser",
    "@phantom/browser-sdk": "browser",
    "react-native": "react-native",
    "reactnative": "react-native",
    "rn": "react-native",
    "mobile": "react-native",
    "@phantom/react-native-sdk": "react-native",
    "cli": "cli",
    "phantom-cli": "cli",
    "@phantom/cli": "cli",
}


def _overview_text() -> str:
    return (
        "Phantom Connect SDK is an open-source multi-platform toolkit for "
        "onboarding users with embedded wallets (Google / Apple) or the "
        "Phantom browser extension. Private keys never enter this agent.\n"
        "\n"
        f"Source: {GITHUB_URL}\n"
        f"Docs: {SDK_OVERVIEW_URL}\n"
        f"Connect modal / spending limits: {CONNECT_URL}\n"
        f"Portal (App ID, allowlisted URLs): {PORTAL_URL}\n"
        "\n"
        "Client SDKs (need a Portal App ID for google/apple):\n"
        f"- React web: {REACT_INSTALL}  (@phantom/react-sdk)\n"
        f"- Vanilla JS / Vue / Angular: {BROWSER_INSTALL}  (@phantom/browser-sdk)\n"
        f"- React Native / Expo: {RN_INSTALL}  (@phantom/react-native-sdk)\n"
        '  Providers: "google", "apple"; web SDKs also support "injected".\n'
        "  Embedded wallets: $1,000 USD/app/day spending limit; sessions last "
        "7 days from last login. Always use signAndSendTransaction — "
        "signTransaction is not supported for embedded wallets.\n"
        "\n"
        "Read the docs from an assistant:\n"
        f"- Docs MCP (read-only): {DOCS_MCP_URL}\n"
        "  Cursor is already wired in .cursor/mcp.json as phantom-docs.\n"
        "  Runtime: set PHANTOM_DOCS_MCP=1.\n"
        f"  Setup: {DOCS_MCP_PAGE}\n"
        "\n"
        "Execute operations (not through this agent):\n"
        f"- CLI: {CLI_INSTALL_COMMAND}  then  phantom login\n"
        f"  {CLI_DOCS_URL}\n"
        f"- Wallet MCP: npx -y @phantom/mcp-server@latest  ({WALLET_MCP_URL}). "
        "BitcoinAgent does not attach it.\n"
        "\n"
        "This agent is read-only: overview, npm package versions, and "
        "`phantom --version`. It does not connect a wallet, login, sign, "
        "send, swap, or run `phantom --mcp`.\n"
        "\n"
        "Not a Bitcoin Core wallet. Coins sent to bitcoin-cli getnewaddress "
        "do not appear in Phantom, and Phantom Bitcoin addresses are not "
        "bitcoind wallets. The window.phantom.bitcoin injected provider is "
        "deprecated — use Wallet Standard or the Connect SDKs.\n"
        "\n"
        "Local:\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom packages\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom status\n"
        f"Docs: {DOCS_URL}"
    )


def _secret_query(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ("seed", "xprv", "private", "secret key", "api key", "recovery phrase")
    )


def resolve_package_keys(text: str) -> list[str]:
    """Map a user query onto PACKAGES keys, or all keys if empty."""
    raw = (text or "").strip()
    if not raw:
        return list(PACKAGES)
    keys: list[str] = []
    seen: set[str] = set()
    for token in raw.replace(",", " ").split():
        alias = _PACKAGE_ALIASES.get(token.lower())
        if alias and alias not in seen:
            keys.append(alias)
            seen.add(alias)
    return keys


def npm_latest_path(package: str) -> str:
    """Return the allowlisted registry path for a scoped package's latest doc."""
    if package not in PACKAGES.values() and package != WALLET_MCP_PACKAGE:
        raise ValueError("Refusing request for an npm package that is not on the allowlist.")
    encoded = urllib.parse.quote(package, safe="@/")
    return f"/{encoded}/latest"


def npm_get_latest(package: str) -> Any:
    """HTTPS GET registry.npmjs.org/<pkg>/latest. Never fetches tarballs."""
    path = npm_latest_path(package)
    url = f"https://{NPM_REGISTRY_HOST}{path}"
    parsed = urllib.request.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError("Refusing request to a host that is not on the allowlist.")
    if not path.endswith("/latest"):
        raise ValueError("Refusing npm request that is not a latest metadata document.")
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "BitcoinAgent/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            raw = response.read(_MAX_BYTES + 1)
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code} from registry.npmjs.org for {package}"}
    except urllib.error.URLError:
        return {"error": "Could not reach registry.npmjs.org. Try again later."}
    if len(raw) > _MAX_BYTES:
        return {"error": "Response from npm was too large."}
    if status != 200:
        return {"error": f"HTTP {status} from registry.npmjs.org for {package}"}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"error": "npm returned a non-JSON body."}
    if not isinstance(payload, dict):
        return {"error": "npm returned a non-object latest document."}
    return payload


def _format_package(package: str, payload: dict[str, Any]) -> str:
    version = payload.get("version") or "unknown"
    description = payload.get("description") or ""
    homepage = payload.get("homepage") or ""
    license_name = payload.get("license") or ""
    lines = [f"- {package}@{version}"]
    if description:
        lines.append(f"  {description}")
    extra = []
    if license_name:
        extra.append(str(license_name))
    if homepage:
        extra.append(str(homepage))
    if extra:
        lines.append("  " + " · ".join(extra))
    return "\n".join(lines)


@tool
def phantom_connect_overview() -> str:
    """Explain Phantom Connect SDKs, Portal App ID, docs MCP, and CLI.

    Read-only. Does not connect a wallet, login, sign, or send.
    """
    return _overview_text()


@tool
def phantom_connect_packages(query: str = "") -> str:
    """Published npm versions for official Phantom Connect SDK packages.

    Pass react, browser, react-native, cli, or a package name. Empty lists
    all client SDKs plus the CLI. Read-only GET to registry.npmjs.org.
    """
    raw = (query or "").strip()
    if _secret_query(raw):
        return "Do not paste seed phrases, private keys, or API keys."
    if raw.lower() in {"mcp", "wallet-mcp", "@phantom/mcp-server", "mcp-server"}:
        return (
            f"{WALLET_MCP_PACKAGE} is the Phantom *wallet* MCP. It can sign, "
            "send, swap, and trade. BitcoinAgent does not attach it.\n"
            f"Install on a machine you control: npx -y {WALLET_MCP_PACKAGE}@latest\n"
            f"Docs: {WALLET_MCP_URL}\n"
            "Use `phantom packages` for the Connect client SDKs and CLI."
        )
    keys = resolve_package_keys(raw)
    if raw and not keys:
        return (
            "Unknown Phantom package. Use react, browser, react-native, cli, "
            "or a name such as @phantom/react-sdk."
        )
    lines = [
        "Phantom Connect SDK packages on npm (latest, read-only):",
    ]
    for key in keys:
        package = PACKAGES[key]
        payload = npm_get_latest(package)
        if isinstance(payload, dict) and payload.get("error"):
            lines.append(f"- {package}: {payload['error']}")
            continue
        if not isinstance(payload, dict):
            lines.append(f"- {package}: unexpected npm payload")
            continue
        lines.append(_format_package(package, payload))
    lines.append(
        "Read-only. This agent will not npm install, connect a wallet, sign, or send."
    )
    lines.append(f"Source: {GITHUB_URL}")
    return "\n".join(lines)


def phantom_cli_path() -> str | None:
    return shutil.which("phantom")


def run_phantom_version(cli_path: str | None = None) -> dict[str, Any]:
    """Run `phantom --version` only. Never login / send / sign / --mcp."""
    binary = cli_path or phantom_cli_path()
    if not binary:
        return {"error": "phantom CLI is not on PATH"}
    try:
        completed = subprocess.run(
            [binary, "--version"],
            check=False,
            capture_output=True,
            timeout=_CLI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"error": "phantom --version timed out"}
    except OSError:
        return {"error": "Could not execute phantom"}
    raw = completed.stdout or completed.stderr
    if len(raw) > _MAX_CLI_BYTES:
        return {"error": "phantom --version returned too much data"}
    try:
        decoded = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return {"error": "phantom --version returned a non-text body"}
    snippet = decoded.splitlines()[0][:200] if decoded else "empty output"
    if completed.returncode != 0:
        return {"error": f"phantom --version failed: {snippet}"}
    return {"version": snippet}


def _app_id_status() -> str:
    if phantom_app_id_set():
        return "PHANTOM_APP_ID: set (not printed)"
    return (
        "PHANTOM_APP_ID: unset — get one from Portal Set Up "
        f"({PORTAL_URL}) if you are integrating a client SDK."
    )


def _docs_mcp_status() -> str:
    if phantom_docs_mcp_enabled():
        return "Runtime docs MCP: attached (PHANTOM_DOCS_MCP)"
    return (
        "Runtime docs MCP: off. Cursor still has phantom-docs in "
        ".cursor/mcp.json. Export PHANTOM_DOCS_MCP=1 to attach it here."
    )


@tool
def phantom_connect_cli_status() -> str:
    """Check whether the official Phantom CLI (`phantom`) is on PATH.

    Read-only. Runs `phantom --version` only. Does not login, send, or sign.
    """
    lines = [
        _app_id_status(),
        _docs_mcp_status(),
    ]
    binary = phantom_cli_path()
    if not binary:
        lines.extend(
            [
                "phantom CLI: not found on PATH.",
                f"Install: {CLI_INSTALL_COMMAND}",
                f"Then: {CLI_DOCS_URL}",
                "BitcoinAgent will not run login, send, sign, or `phantom --mcp`. "
                "Use the official CLI on a machine you control if you need a wallet.",
            ]
        )
        return "\n".join(lines)
    payload = run_phantom_version(binary)
    if payload.get("error"):
        lines.extend(
            [
                f"phantom CLI: {binary}",
                str(payload["error"]),
                "Status is read-only. BitcoinAgent will not run login, send, sign, or --mcp.",
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            f"phantom CLI: {binary}",
            f"Version: {payload.get('version')}",
            "BitcoinAgent only checks the version. Login, send, sign, and "
            "`phantom --mcp` stay in the official CLI — not here.",
        ]
    )
    return "\n".join(lines)
