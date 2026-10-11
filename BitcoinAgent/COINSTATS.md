# CoinStats

CoinStats is a crypto market-data and portfolio platform. The hosted
MCP server at `https://mcp.coinstats.app/mcp` exposes prices, wallets,
DeFi, portfolios, exchanges, and news over Streamable HTTP. Cursor
authorises it with OAuth 2.1 (PKCE); BitcoinAgent talks to the same
REST surface with an optional `X-API-KEY`.

This agent is **read-only**. It does **not** add transactions, connect
wallets or exchanges, sync, or delete portfolios.

Official docs:

- Product / MCP landing: https://coinstats.app/mcp/
- Connect (OAuth): https://coinstats.app/api-docs/mcp/connecting/
- MCP tool catalog: https://coinstats.app/api-docs/mcp/tools/
- llms.txt index: https://coinstats.app/docs/llms.txt
- REST reference: https://coinstats.app/api-docs/
- API dashboard (optional key): https://openapi.coinstats.app
- Source (stdio fallback): https://github.com/CoinStatsHQ/coinstats-mcp

## What this agent will do

| Action | How |
| --- | --- |
| Use CoinStats in Cursor | `.cursor/mcp.json` `coinstats` → `https://mcp.coinstats.app/mcp` (OAuth) |
| Explain MCP + REST | `coinstats_overview` |
| Coin price / market | `coinstats_coin` → `GET https://api.coinstats.app/v1/coins/{id}` |
| Global market cap | `coinstats_markets` → `GET https://api.coinstats.app/v1/markets` |
| List your portfolios | `coinstats_portfolio_list` → `GET …/v1/portfolio/list` |
| Portfolio coins + PnL | `coinstats_portfolio` → `GET …/v1/portfolio/coins` |
| Public wallet balance | `coinstats_wallet` → `GET …/v1/wallet/balance` |
| Key present? | `coinstats_status` (never prints the key) |

REST calls need `COINSTATS_API_KEY` (sent as `X-API-KEY`, never logged).
Create a key at https://openapi.coinstats.app. Cursor MCP uses OAuth
instead and does not need that env var.

## What this agent will not do

`add-portfolio-transaction`, `connect-portfolio-wallet`,
`connect-portfolio-exchange`, `sync-portfolio`, and `delete-portfolio`
stay in the hosted MCP or the official REST API on a machine you
control. BitcoinAgent does **not** attach those write tools. It never
sends share tokens or portfolio passcodes.

Headless stdio MCP (developer API key, no browser OAuth):

```bash
export COINSTATS_API_KEY=your_key
npx -y @coinstats/coinstats-mcp
```

That process still exposes write tools. Do not attach it here.

## Cursor (local agents)

`.cursor/mcp.json` already includes the hosted server:

| Server | URL | Auth |
| --- | --- | --- |
| `coinstats` | `https://mcp.coinstats.app/mcp` | OAuth 2.1 / PKCE (Cursor opens a browser) |

Restart Cursor. The first tool call opens
`coinstats.app/openapi/consent`. Approve read access. Dynamic Client
Registration is supported; no pre-shared `client_id` is needed.

BitcoinAgent does not attach the hosted MCP at runtime because those
tools can mutate portfolios. AgentCore Gateway also cannot complete a
browser OAuth flow. The runtime talks to `api.coinstats.app` directly.

## Check from this tree (no AWS)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats coin bitcoin
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats markets
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats portfolio
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats portfolio list
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats wallet bc1q… bitcoin
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats status
```

Known coin ids / symbols: bitcoin (BTC), ethereum (ETH), solana (SOL),
tether (USDT), usd-coin (USDC), plus any CoinStats `coinId` slug.

## Not the same as Bitcoin Core

CoinStats prices and portfolio rows are CoinStats' market data, not
`bitcoin-cli getbalance`. A receive address from `getnewaddress` is not
a CoinStats portfolio until you track it in the CoinStats app. Use
`fees`, `tip`, `tx`, and `receive` for Bitcoin public chain data.
