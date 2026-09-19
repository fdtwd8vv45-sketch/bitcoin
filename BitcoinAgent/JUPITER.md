# Jupiter

Jupiter is Solana DeFi infrastructure. APIs are REST/JSON, need no RPC
node, and return clean responses that agents can parse. BitcoinAgent
connects to the **docs** and to **read-only** Price / Tokens / VRFD
eligibility lookups. It does **not** swap, place orders, lend, sign, or
submit Express Verification payments.

Official docs:

- AI overview: https://developers.jup.ag/docs/ai
- Documentation index (llms.txt): https://dev.jup.ag/docs/llms.txt
- Skills: https://developers.jup.ag/docs/ai/skills
- Docs MCP: https://developers.jup.ag/docs/mcp
- CLI: https://developers.jup.ag/docs/ai/cli
- Trading MCP (not attached here): https://mcp.jup.ag
- Price API: https://developers.jup.ag/docs/price
- Tokens API: https://developers.jup.ag/docs/tokens
- Express Verification: https://developers.jup.ag/docs/tokens/verification
- Portal (optional API key): https://developers.jup.ag/portal

## What this agent will do

| Action | How |
| --- | --- |
| Read Jupiter docs | Cursor `jupiter-docs` MCP, or `JUPITER_DOCS_MCP=1` on the runtime |
| USD prices | `jupiter_price` → `GET https://api.jup.ag/price/v3` |
| Token search | `jupiter_token_search` → `GET https://api.jup.ag/tokens/v2/search` |
| VRFD Express eligibility | `jupiter_verify_eligibility` → `GET …/tokens/v2/verify/express/check-eligibility` |
| CLI present? | `jup --version` only |

Keyless Price / Tokens access is 0.5 RPS. Export `JUPITER_API_KEY` (sent
as the `x-api-key` header, never logged) for a higher limit.

## What this agent will not do

Swap, limit orders, DCA, lend, prediction markets, transaction landing,
and **Express Verification submit** (`craft-txn` / sign / `execute`) stay
in the official Jupiter CLI or Trading MCP / VRFD API. BitcoinAgent does
not attach `https://mcp.jup.ag` because those tools can move funds. Each
Express submission costs 1000 JUP (or SOL, USDC, or JUPUSD swapped to
1000 JUP via Ultra). The free Standard flow is on
[verified.jup.ag](https://verified.jup.ag).

On a machine you control:

```bash
npm i -g @jup-ag/cli
npx skills add jup-ag/agent-skills --skill "integrating-jupiter"
```

## Cursor (local agents)

`.cursor/mcp.json` already includes the read-only docs server:

| Server | URL | Auth |
| --- | --- | --- |
| `jupiter-docs` | `https://developers.jup.ag/docs/mcp` | none |

BitcoinAgent attaches the same server when `JUPITER_DOCS_MCP=1` or
`JUPITER_API_KEY` is set. AgentCore Gateway cannot send an API key to an
MCP target, so the runtime talks to Jupiter directly.

## Check from this tree (no AWS)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter price SOL,JUP
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter token JUP
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter verify USDC
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter status
```

Known price symbols: SOL, USDC, USDT, JUP, JupUSD, JupSOL, JLP — or a
mint address. Ticker search can return copycats; prefer `isVerified` and
the mint in the table above.

## Express Verification (read-only eligibility)

Jupiter VRFD Express is a paid three-step flow: check eligibility, craft a
1000 JUP payment transaction, sign it, then execute. BitcoinAgent only
does step 1 (`check-eligibility`). It never returns an unsigned payment
transaction and never calls `/execute`.

`paymentCurrency` is a symbol (`JUP`, `SOL`, `USDC`, `JUPUSD`), not a
mint. Non-JUP currencies swap to 1000 JUP via Ultra on a machine you
control — not here.

If both `canVerify` and `canMetadata` are false, Express rejects the
submission before charging. Track requests at
https://verified.jup.ag/tokens/browse

## Not the same as Bitcoin Core

Jupiter prices and token metadata are Solana. A Bitcoin receive address
or txid will not work here; use `fees`, `tip`, `tx`, and `receive` for
Bitcoin public data.
