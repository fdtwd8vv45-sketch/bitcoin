"""Read-only cubic MCP overview and status.

Cursor uses the hosted MCP at https://www.cubic.dev/api/mcp via OAuth.
BitcoinAgent does not attach that server: AgentCore Gateway cannot
complete browser OAuth, and the catalog includes write tools (trigger
review, update issues, billing, secrets).

Optional CUBIC_API_KEY is detected only. Callers must not print or send it.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from mcp_client.settings import cubic_api_key_set
from optional_tool import tool

MCP_URL = "https://www.cubic.dev/api/mcp"
MCP_DOCS_URL = "https://docs.cubic.dev/ide/mcp-server"
AGENT_SETUP_URL = "https://docs.cubic.dev/ide/agent-setup"
CLI_DOCS_URL = "https://docs.cubic.dev/ide/cli-review"
QUICKSTART_URL = "https://docs.cubic.dev/ai-review/quickstart"
LANDING_URL = "https://www.cubic.dev"
CLI_INSTALL_CURL = "curl -fsSL https://cubic.dev/install | bash"
CLI_INSTALL_NPX = "npx @cubic-dev-ai/cli install -g"
CLI_PACKAGE = "@cubic-dev-ai/cli"
_CLI_TIMEOUT_SECONDS = 8
_MAX_CLI_BYTES = 8_000

# Hosted MCP tools that mutate reviews, billing, or repository setup.
# Not attached here. Names stay in docs so tests can prove we refuse them.
WRITE_TOOLS = (
    "trigger_pr_review",
    "update_pr_issue_status",
    "set_pr_auto_fix",
    "update_issue_status",
    "update_member_seat",
    "update_subscription",
    "update_flex_capacity",
    "update_session_environment",
    "create_secrets_upload",
)


def _overview_text() -> str:
    writes = ", ".join(WRITE_TOOLS)
    return (
        "cubic is an AI code-review platform. The hosted MCP server exposes "
        "PR review issues, codebase wikis, scans, learnings, billing, and "
        "team tools over Streamable HTTP.\n"
        "\n"
        f"Endpoint (exact URL): {MCP_URL}\n"
        "  Use www.cubic.dev, not cubic.dev — OAuth clients compare the "
        "protected-resource origin exactly.\n"
        f"MCP docs: {MCP_DOCS_URL}\n"
        f"IDE setup: {AGENT_SETUP_URL}\n"
        f"Local CLI review: {CLI_DOCS_URL}\n"
        f"Quickstart: {QUICKSTART_URL}\n"
        "\n"
        "Cursor is already wired in .cursor/mcp.json as cubic "
        "(type: http, OAuth). Connect in MCP settings and complete the "
        "browser sign-in. No Authorization header or cbk_ key belongs in "
        "that file.\n"
        "\n"
        "BitcoinAgent does not attach the hosted MCP at runtime. AgentCore "
        "Gateway cannot complete a browser OAuth flow, and these write "
        f"tools are not attached: {writes}.\n"
        "\n"
        "Read tools such as get_pr_issues, list_wikis, get_wiki_page, "
        "list_scans, get_issue, and list_learnings stay in Cursor after "
        "you connect. get_pr_issues lists published findings; it does "
        "not start a review.\n"
        "\n"
        "Local reviews need the official CLI, not MCP:\n"
        f"  {CLI_INSTALL_CURL}\n"
        f"  or: {CLI_INSTALL_NPX}\n"
        "  cubic            # browser sign-in\n"
        "  cubic review     # uncommitted changes\n"
        "  cubic review -b  # branch vs detected base\n"
        "\n"
        "Optional CUBIC_API_KEY (starts with cbk_) is for the official "
        "CLI in CI / cloud agents. This agent never sends or prints it.\n"
        "\n"
        "This agent is read-only: overview and status. It does not start "
        "reviews, change issue state, update seats or subscriptions, or "
        "upload repository secrets.\n"
        "\n"
        "Not Bitcoin Core review. CONTRIBUTING.md stays on howto contribute.\n"
        "\n"
        "Local:\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py cubic\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py cubic status\n"
        f"Product: {LANDING_URL}"
    )


def cubic_cli_path() -> str | None:
    return shutil.which("cubic")


def run_cubic_version(cli_path: str | None = None) -> dict[str, Any]:
    """Run `cubic --version` only. Never review, login, or send a key."""
    binary = cli_path or cubic_cli_path()
    if not binary:
        return {"error": "cubic CLI is not on PATH"}
    try:
        completed = subprocess.run(
            [binary, "--version"],
            check=False,
            capture_output=True,
            timeout=_CLI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"error": "cubic --version timed out"}
    except OSError:
        return {"error": "Could not execute cubic"}
    raw = completed.stdout or completed.stderr
    if len(raw) > _MAX_CLI_BYTES:
        return {"error": "cubic --version returned too much data"}
    try:
        decoded = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return {"error": "cubic --version returned a non-text body"}
    snippet = decoded.splitlines()[0][:200] if decoded else "empty output"
    if completed.returncode != 0:
        return {"error": f"cubic --version failed: {snippet}"}
    return {"version": snippet}


def _key_status() -> str:
    if cubic_api_key_set():
        return "CUBIC_API_KEY: set (not printed; not sent by this agent)"
    return (
        "CUBIC_API_KEY: unset — Cursor MCP uses OAuth instead. Generate a "
        "personal key at Settings > API, CLI & MCP only for the official "
        "CLI in CI."
    )


def _mcp_status() -> str:
    return (
        f"Cursor MCP: {MCP_URL} (OAuth; already in .cursor/mcp.json)\n"
        "Runtime MCP: not attached (write tools stay off)"
    )


@tool
def cubic_overview() -> str:
    """Explain cubic's hosted MCP and what this agent will not do.

    Cursor is already wired in .cursor/mcp.json. This runtime does not
    attach the server because it includes review, billing, and secret
    write tools.
    """
    return _overview_text()


@tool
def cubic_status() -> str:
    """Report cubic Cursor MCP, CUBIC_API_KEY, and `cubic --version`.

    Never prints the API key. Never attaches the hosted MCP. Never runs
    `cubic review`.
    """
    lines = [_key_status(), _mcp_status()]
    binary = cubic_cli_path()
    if not binary:
        lines.extend(
            [
                "cubic CLI: not found on PATH.",
                f"Install: {CLI_INSTALL_CURL}",
                f"or: {CLI_INSTALL_NPX}",
                f"Then: {CLI_DOCS_URL}",
                "BitcoinAgent will not run review, login, or send CUBIC_API_KEY. "
                "Use the official CLI on a machine you control for local reviews.",
            ]
        )
        return "\n".join(lines)
    payload = run_cubic_version(binary)
    if "error" in payload:
        lines.append(f"cubic CLI: {payload['error']}")
    else:
        lines.append(f"cubic CLI: {payload['version']}")
    lines.append(
        "Read-only. This agent will not run `cubic review` or attach "
        "trigger_pr_review / update_subscription / create_secrets_upload."
    )
    return "\n".join(lines)
