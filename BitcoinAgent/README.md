# BitcoinAgent

A Bitcoin Core assistant for this tree: JSON-RPC help, docs, contributor
workflow, and public chain status. After deploy it can also remember users
and search the web.

You do **not** need AWS to use the tools.

## Try it now (no AWS, no Bedrock)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py "What does getblockcount do?"
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py rpc sendtoaddress
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py receive
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py receive <address-or-txid>
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py source 0xdAC17F958D2ee523a2206206994597C13D831ec7
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py agentic
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py agentic status
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter price SOL,JUP
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter verify USDC
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom packages
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats coin bitcoin
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats portfolio
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py cubic
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py cubic status
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl inspect path/to/file.BNDL
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl extract path/to/file.BNDL hello.txt
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko plan path/to/images.apko.json
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution eth_blockNumber
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats snapshot
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py   # interactive prompt
```

Or from this directory: `make tools`. That path calls the same read-only
tools the hosted agent uses. It does not start a model.

See what is still missing for a live model / deploy:

```bash
./BitcoinAgent/scripts/doctor.sh
```

## What was still painful, and what this adds

The first revision needed the AgentCore CLI, Node, uv, AWS credentials, and
Bedrock just to ask what `getblockcount` does. Memory also required a
hand-minted UUID session id, and Cedar needed a gateway ARN pasted by hand.

| Friction | Now |
| --- | --- |
| Cannot try anything without AWS | `local_cli.py` / `make tools` |
| "What else do I need?" | `scripts/doctor.sh` |
| Wallet RPCs missing from the index | Parser now picks up non-`static` `RPCMethod` plus `bumpfee` wrappers |
| Session UUID ceremony | Clients reuse `~/.bitcoin-agent/session.json`; `--new-session` to rotate |
| After-deploy ARN / Cedar steps | `scripts/after_deploy.sh` writes `.local/deploy.env` and a filled Cedar file |
| Memory only after deploy | Local `remember` / `notes` (never store secrets). Same tools are attached in `agentcore dev` when memory is unset |
| "Did I mess up a receive?" | `receive` / `check_receive` — checklist plus public address/txid lookup |

Still requires **your** AWS account: live Claude, AgentCore Memory, gateway
web search, online evals. This environment cannot deploy those.

## Tools

| Tool | Purpose |
| --- | --- |
| `lookup_rpc` | Explain a JSON-RPC method from the C++ source / bundled index |
| `list_rpc_methods` | List methods, optionally by category |
| `search_docs` | Search Bitcoin Core markdown docs |
| `developer_howto` | Short guides for `build`, `test`, `contribute`, `rpc`, `agent`, `local`, `receive`, `wallet`, `agentic`, `jupiter`, `phantom`, `coinstats`, `cubic`, `libbndl`, `apko`, `execution`, `etherscan-stats` |
| `recommended_fees` | Live fee estimates from mempool.space |
| `chain_tip_height` | Current Bitcoin tip height |
| `difficulty_adjustment` | Difficulty-adjustment estimate |
| `lookup_transaction` | Public tx lookup by 64-char hex txid |
| `lookup_address` | Public totals for a Bitcoin mainnet address |
| `lookup_contract_source` | Verified EVM contract source, ABI, and compiler settings (Etherscan `getsourcecode`) |
| `check_receive` | Tell a receive delay from a wrong address / network |
| `remember_note` / `recall_notes` | Local notes when AgentCore Memory is unset |
| `agentic_wallet_overview` / `agentic_wallet_status` | OKX Agentic Wallet overview + read-only `onchainos` CLI status |
| `jupiter_overview` / `jupiter_price` / `jupiter_token_search` / `jupiter_verify_eligibility` / `jupiter_cli_status` | Jupiter docs overview, USD prices, token search, VRFD Express eligibility, read-only `jup --version` |
| `phantom_connect_overview` / `phantom_connect_packages` / `phantom_connect_cli_status` | Phantom Connect SDK overview, npm latest versions, read-only `phantom --version` |
| `coinstats_overview` / `coinstats_coin` / `coinstats_markets` / `coinstats_portfolio_list` / `coinstats_portfolio` / `coinstats_wallet` / `coinstats_status` | CoinStats MCP overview, prices, global market, portfolio list/coins + PnL, one-chain wallet balance |
| `cubic_overview` / `cubic_status` | cubic hosted MCP overview + OAuth / CLI status (never prints `CUBIC_API_KEY`) |
| `libbndl_overview` / `inspect` / `lookup` / `types` / `extract` / `create` / `add` / `replace` / `fetch` | Criterion/EA BUNDLE tools pinned to Bo98/libbndl@2b88eff (inspect, GetBinary extract, BND2 save, http(s) fetch) |
| `apko_smoke_overview` / `plan` / `status` / `preflight` / `run` | APKO smoke contract pinned to ethereum-optimism/actions@7eaff21e (factory@b87283a8: Docker daemon + pull/arch preflight) |
| `execution_apis_overview` / `method` / `list` / `graphql` / `contribute` | Ethereum Execution APIs spec pinned to ethereum/execution-apis@34151926 (OpenRPC JSON-RPC + EIP-1767 GraphQL; never calls a node) |
| `etherscan_stats_overview` / `etherscan_stats` / `etherscan_eth_supply` / `etherscan_eth_price` / `etherscan_node_count` / `etherscan_gas_oracle` / `etherscan_stats_status` | Free Etherscan charts/stats (`ethsupply2`, `ethprice`, `nodecount`, `gasoracle`); never calls PRO daily endpoints |
| Gateway `WebSearch` | After deploy: search BIPs and public discussion |
| Etherscan MCP | Optional. Set `ETHERSCAN_API_KEY` for official EVM data + docs MCP |
| Jupiter docs MCP | Optional. Set `JUPITER_DOCS_MCP=1` (or `JUPITER_API_KEY`) for Jupiter docs MCP |
| Phantom docs MCP | Optional. Set `PHANTOM_DOCS_MCP=1` for Phantom Connect SDK docs MCP |
| CoinStats MCP | Optional. Cursor OAuth at `mcp.coinstats.app`; REST needs `COINSTATS_API_KEY` |
| cubic MCP | Optional. Cursor OAuth at `www.cubic.dev/api/mcp`; write tools are not attached |

Refresh the bundled index after RPC changes:

```bash
make -C BitcoinAgent index
# or:
cd BitcoinAgent/app/BitcoinAgent
python3 generate_rpc_index.py
python3 -m unittest discover -s tests
```

## Live model (needs AWS + Bedrock)

```bash
# Node 20+, uv, and AWS credentials with Bedrock model access
npm install -g @aws/agentcore
cd BitcoinAgent
agentcore dev
```

In another terminal:

```bash
cd BitcoinAgent
agentcore invoke --dev "What does getblockcount do?"
```

The local server defaults to port **8080**. AgentCore Memory and gateway URLs
are not injected until you deploy. In that mode the agent falls back to
local notes.

## Etherscan MCP (optional)

Official Etherscan MCP servers are configured for Cursor in
[`.cursor/mcp.json`](../.cursor/mcp.json). The same key also enables the
local `source` / `lookup_contract_source` tool, which calls Etherscan API
v2 `module=contract&action=getsourcecode` on `api.etherscan.io` (allowlisted
HTTPS GET), and the free `etherscan-stats` tools (`ethsupply2`,
`ethprice`, `nodecount`, `gasoracle`). Create a key at
https://etherscan.io/apidashboard and export it before starting Cursor,
the local CLI, or the live agent:

```bash
export ETHERSCAN_API_KEY=your_key
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py source 0xdAC17F958D2ee523a2206206994597C13D831ec7
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py source 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 arbitrum
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats snapshot
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats supply
```

Pass a numeric `chainid` or a name such as `ethereum`, `arbitrum`, or `base`
(default: Ethereum `1`). Unverified addresses are reported as unverified
instead of guessed. Proxy metadata is returned; fetch the implementation
address separately for the logic contract. The tool never executes source
and never prints the API key.

| Server | URL | Auth |
| --- | --- | --- |
| `etherscan` | `https://mcp.etherscan.io/mcp` | `Authorization: Bearer $ETHERSCAN_API_KEY` |
| `etherscan-docs` | `https://docs.etherscan.io/mcp` | none |

BitcoinAgent attaches the same servers when `ETHERSCAN_API_KEY` is set
(docs-only: `ETHERSCAN_DOCS_MCP=1`). AgentCore Gateway cannot send an API
key to an MCP target, so the runtime talks to Etherscan directly. The
tools are read-only and count against your Etherscan quota. Docs:
https://docs.etherscan.io/api-reference/endpoint/getsourcecode
and https://docs.etherscan.io/endpoint-showcase/charts-and-stats.
See [ETHERSCAN_STATS.md](ETHERSCAN_STATS.md).

## Jupiter (optional)

Jupiter APIs are REST/JSON on Solana (no RPC node). BitcoinAgent reads the
docs and does keyless Price / Tokens lookups plus a read-only VRFD Express
eligibility check. It does not swap, place orders, sign, or submit Express
payments. See [JUPITER.md](JUPITER.md).

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter price SOL,JUP
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter token JUP
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter verify USDC
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py jupiter status
```

Price and Tokens work without a key at 0.5 RPS. For a higher limit:

```bash
export JUPITER_API_KEY=jup_...   # from https://developers.jup.ag/portal
```

| Server | URL | Auth |
| --- | --- | --- |
| `jupiter-docs` | `https://developers.jup.ag/docs/mcp` | none |

Cursor is already wired in [`.cursor/mcp.json`](../.cursor/mcp.json).
BitcoinAgent attaches the same docs MCP when `JUPITER_DOCS_MCP=1` or
`JUPITER_API_KEY` is set. Trading MCP (`https://mcp.jup.ag`) is not
attached. Official CLI / skills (on a machine you control):

```bash
npm i -g @jup-ag/cli
npx skills add jup-ag/agent-skills --skill "integrating-jupiter"
```

## Phantom Connect SDK (optional)

[Phantom Connect SDK](https://github.com/phantom/phantom-connect-sdk) is
the open-source React / Browser / React Native toolkit for embedded
wallets (Google / Apple) or the Phantom extension. BitcoinAgent reads
the docs and looks up npm versions. It does not connect a wallet, login,
sign, or send. See [PHANTOM.md](PHANTOM.md).

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom packages
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom status
```

| Server | URL | Auth |
| --- | --- | --- |
| `phantom-docs` | `https://docs.phantom.com/mcp` | none |

Cursor is already wired in [`.cursor/mcp.json`](../.cursor/mcp.json).
BitcoinAgent attaches the same docs MCP when `PHANTOM_DOCS_MCP=1`.
Wallet MCP (`@phantom/mcp-server`) is not attached. Official CLI (on a
machine you control):

```bash
npm install -g @phantom/cli
```

## CoinStats (optional)

[CoinStats](https://coinstats.app/mcp/) is crypto market data plus
portfolios. Cursor uses the hosted MCP at
`https://mcp.coinstats.app/mcp` (OAuth 2.1). BitcoinAgent reads the
same REST API for prices, global market cap, your portfolios + PnL, and
a public wallet balance. It does not add transactions, connect wallets
or exchanges, sync, or delete portfolios. See [COINSTATS.md](COINSTATS.md).

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats coin bitcoin
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats markets
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats portfolio
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats wallet bc1q… bitcoin
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py coinstats status
```

REST calls need a dashboard key:

```bash
export COINSTATS_API_KEY=your_key   # from https://openapi.coinstats.app
```

| Server | URL | Auth |
| --- | --- | --- |
| `coinstats` | `https://mcp.coinstats.app/mcp` | OAuth 2.1 / PKCE (Cursor) |

Cursor is already wired in [`.cursor/mcp.json`](../.cursor/mcp.json).
BitcoinAgent does not attach the hosted MCP at runtime because those
tools can mutate portfolios. The runtime talks to `api.coinstats.app`
directly when `COINSTATS_API_KEY` is set.

## cubic (optional)

[cubic](https://www.cubic.dev) is an AI code-review platform. The hosted
MCP at `https://www.cubic.dev/api/mcp` (Streamable HTTP + OAuth) exposes
PR review issues, wikis, scans, learnings, billing, and team tools.
BitcoinAgent only explains the endpoint. It does not attach the server,
start reviews, change issue state, or manage seats. See
[CUBIC.md](CUBIC.md).

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py cubic
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py cubic status
```

| Server | URL | Auth |
| --- | --- | --- |
| `cubic` | `https://www.cubic.dev/api/mcp` | OAuth (Cursor) |

Cursor is already wired in [`.cursor/mcp.json`](../.cursor/mcp.json).
Use the exact `www.cubic.dev` URL. BitcoinAgent does not attach the
hosted MCP at runtime because those tools can trigger reviews, update
issues, change billing, and upload secrets.

## libbndl (optional)

[libbndl](https://github.com/Bo98/libbndl) reads and writes Criterion/EA
BUNDLE archives. BitcoinAgent pins
[2b88eff](https://github.com/Bo98/libbndl/tree/2b88effe9278dd832f7a1771a472cd4db0dbc072)
(non-Xbox BNDL, BNDL v3/v4): inspect, extract, create/add/replace (BND2
PC), and http(s) fetch. See [LIBBNDL.md](LIBBNDL.md).

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl inspect path/to/file.BNDL
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl extract path/to/file.BNDL hello.txt
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl create /tmp/out.bnd2 hello.txt TextFile ./hello.txt
```

## APKO smoke tests (optional)

APKO image smoke tests are pinned to
[ethereum-optimism/actions@7eaff21e](https://github.com/ethereum-optimism/actions/commit/7eaff21e45042406c7e5602f04bcabe959c36047),
which pins factory
[b87283a8](https://github.com/ethereum-optimism/factory/commit/b87283a8bb6c325da0ef18400eb819b5979a9bd3).
amd64 jobs default to `ubuntu-24.04` (a Docker daemon), and image pull
plus architecture checks fail **before** the command loop. See
[APKO.md](APKO.md).

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko plan path/to/images.apko.json
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py apko preflight alpine:3.20 amd64
```

## Ethereum Execution APIs (optional)

The [Execution API specification](https://github.com/ethereum/execution-apis)
is the canonical JSON-RPC (OpenRPC) plus GraphQL interface every Ethereum
execution client implements. BitcoinAgent looks up that **spec** at pin
[34151926](https://github.com/ethereum/execution-apis/commit/34151926fbf395e66797add1f60fd759681678e6).
It does not connect to a node, sign, send, or call `engine_*`. See
[EXECUTION_APIS.md](EXECUTION_APIS.md).

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution eth_blockNumber
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution list eth
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution graphql
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution contribute
```

Quickstart (compile YAML → `openrpc.json`, Docusaurus, hive):
https://ethereum.github.io/execution-apis/docs/quickstart/

## Agentic Wallet (optional)

OKX Agentic Wallet keeps key generation, storage, and signing inside a TEE.
Sign in with email, Google, or Apple. BitcoinAgent only explains the product
and can run read-only `onchainos wallet status`. It does not send, swap, or
sign. See [AGENTIC_WALLET.md](AGENTIC_WALLET.md).

```bash
npx -y @okxweb3/onchainos-installer install   # Node.js 18+
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py agentic
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py agentic status
```

## Deploy

```bash
cd BitcoinAgent
agentcore deploy
./scripts/after_deploy.sh
set -a && source .local/deploy.env && set +a
python3 clients/python/invoke_agent.py "My name is Alex and I work on Bitcoin Core RPC tests"
```

`after_deploy.sh` collects runtime/gateway ARNs, writes a reusable session,
and fills `policies/allow_read_tools.cedar.template`. Review the Cedar file
before attaching it. See `PRODUCTION.md`.

App clients (`clients/python/invoke_agent.py`, `clients/typescript/invoke_agent.ts`)
reuse one session id per person automatically.

# AgentCore Project

This project was created with the [AgentCore CLI](https://github.com/aws/agentcore-cli).

## Project Structure

```
BitcoinAgent/
├── AGENTS.md
├── PRODUCTION.md
├── Makefile                 # tools / doctor / test / index
├── scripts/                 # doctor, after_deploy, quality-gate
├── clients/                 # IAM SigV4 invoke helpers
├── policies/
├── agentcore/               # agentcore.json, CDK, aws-targets
└── app/BitcoinAgent/        # runtime + local CLI
```

## Getting Started

### Prerequisites

- **For the tools only:** Python 3.10+
- **For the live agent:** Node.js 20+, [uv](https://docs.astral.sh/uv/getting-started/installation/), AWS credentials, Bedrock model access
- **Docker** only for Container build agents

### Development

```bash
agentcore dev
```

### Deployment

```bash
agentcore deploy
./scripts/after_deploy.sh
```

## Commands

| Command | Description |
| --- | --- |
| `make tools` / `local_cli.py` | Call tools with no AWS |
| `./scripts/doctor.sh` | Check Python, index, tests, and AWS toolchain |
| `./scripts/after_deploy.sh` | Write ARNs, session, and filled Cedar |
| `agentcore dev` | Run agent locally with hot-reload |
| `agentcore deploy` | Deploy to AWS via CDK |
| `agentcore invoke` | Invoke agent (local or deployed) |
| `agentcore status` | Show deployment status |
| `agentcore validate` | Validate configuration |
| `agentcore logs` | View agent logs |

## Resources

| Resource | Purpose |
| --- | --- |
| Agent (runtime) | HTTP agent deployed to AgentCore Runtime |
| Memory | Persistent context (`BitcoinMemory`) after deploy |
| Gateway | MCP gateway + WebSearch after deploy |
| Policy | Cedar engine (`BitcoinPolicy`, starts LOG_ONLY) |
| Evaluator | `BitcoinAccuracy` plus built-in quality evaluators |

## Documentation

- [Jupiter](JUPITER.md) — Jupiter APIs, docs MCP, Price/Tokens, VRFD eligibility (read-only in this agent)
- [Phantom Connect](PHANTOM.md) — Phantom Connect SDKs, docs MCP, npm versions (read-only in this agent)
- [CoinStats](COINSTATS.md) — CoinStats MCP (Cursor OAuth) + read-only prices / portfolio / wallet
- [cubic](CUBIC.md) — cubic MCP (Cursor OAuth); write tools are not attached
- [libbndl](LIBBNDL.md) — Criterion/EA BUNDLE inspect/lookup, pinned to Bo98/libbndl@2b88eff
- [APKO](APKO.md) — APKO smoke plan/preflight, pinned to ethereum-optimism/actions@7eaff21e
- [Execution APIs](EXECUTION_APIS.md) — Ethereum JSON-RPC OpenRPC + GraphQL spec lookup, pinned to ethereum/execution-apis@34151926
- [Agentic Wallet](AGENTIC_WALLET.md) — OKX TEE wallet overview (read-only in this agent)
- [AgentCore CLI](https://github.com/aws/agentcore-cli)
- [AgentCore CDK Constructs](https://github.com/aws/agentcore-l3-cdk-constructs)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
