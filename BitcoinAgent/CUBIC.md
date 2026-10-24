# cubic

[cubic](https://www.cubic.dev) is an AI code-review platform. The hosted
MCP server at `https://www.cubic.dev/api/mcp` exposes PR review issues,
codebase wikis, scans, learnings, billing, and team tools over
Streamable HTTP. Cursor authorises it with OAuth; some clients can send
a personal `cbk_` API key as a bearer token instead.

This agent is **read-only**. It does **not** attach the hosted MCP, start
reviews, change issue state, update seats or subscriptions, or upload
repository secrets.

Official docs:

- MCP server: https://docs.cubic.dev/ide/mcp-server
- Connect cubic to your IDE: https://docs.cubic.dev/ide/agent-setup
- Local CLI review: https://docs.cubic.dev/ide/cli-review
- Developer quickstart: https://docs.cubic.dev/ai-review/quickstart
- Settings (API key): https://www.cubic.dev (Settings > API, CLI & MCP)

Use the exact URL `https://www.cubic.dev/api/mcp`. Some OAuth clients
reject `https://cubic.dev/api/mcp` because the protected-resource origin
does not match.

## What this agent will do

| Action | How |
| --- | --- |
| Use cubic in Cursor | `.cursor/mcp.json` `cubic` → `https://www.cubic.dev/api/mcp` (OAuth) |
| Explain MCP + CLI | `cubic_overview` |
| Key / CLI present? | `cubic_status` (never prints `CUBIC_API_KEY`) |

After Cursor connects, ask it to list open review issues on a PR you
can access. That uses `get_pr_issues`. It does not start a review.

## What this agent will not do

These hosted MCP tools stay in Cursor (or the official CLI) on a
machine you control:

- `trigger_pr_review`
- `update_pr_issue_status`
- `set_pr_auto_fix`
- `update_issue_status`
- `update_member_seat`
- `update_subscription`
- `update_flex_capacity`
- `update_session_environment`
- `create_secrets_upload`

BitcoinAgent does **not** attach the hosted MCP at runtime. AgentCore
Gateway cannot complete a browser OAuth flow, and the catalog includes
those write tools. Optional `CUBIC_API_KEY` is detected only so status
can say set/unset; this agent never sends the key.

Local reviews need the official CLI, not MCP:

```bash
curl -fsSL https://cubic.dev/install | bash
# or: npx @cubic-dev-ai/cli install -g
cubic            # browser sign-in
cubic review     # uncommitted changes
cubic review -b  # branch vs detected base
```

In CI or cloud agents, store a personal key as `CUBIC_API_KEY` and skip
the browser sign-in. Keys start with `cbk_` and cubic only shows the
full value once. Regenerating the key replaces it for the CLI, MCP,
Members API, and Analytics API.

## Cursor (local agents)

`.cursor/mcp.json` already includes the hosted server:

| Server | URL | Auth |
| --- | --- | --- |
| `cubic` | `https://www.cubic.dev/api/mcp` | OAuth (Cursor opens a browser) |

Restart Cursor. Open MCP settings, connect cubic, and complete the
browser sign-in. No `Authorization` header or API key belongs in
`.cursor/mcp.json`.

Cursor Agent (same config):

```bash
agent mcp enable cubic
agent mcp login cubic
agent mcp list-tools cubic
```

## Check from this tree (no AWS)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py cubic
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py cubic status
```

## Not the same as Bitcoin Core review

cubic reviews GitHub pull requests and local diffs. It is not
`test/functional/test_runner.py` and it does not replace Bitcoin Core
code review. Use `howto contribute` for CONTRIBUTING.md.
