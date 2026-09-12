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
| `developer_howto` | Short guides for `build`, `test`, `contribute`, `rpc`, `agent`, `local`, `receive` |
| `recommended_fees` | Live fee estimates from mempool.space |
| `chain_tip_height` | Current Bitcoin tip height |
| `difficulty_adjustment` | Difficulty-adjustment estimate |
| `lookup_transaction` | Public tx lookup by 64-char hex txid |
| `lookup_address` | Public totals for a Bitcoin mainnet address |
| `check_receive` | Tell a receive delay from a wrong address / network |
| `remember_note` / `recall_notes` | Local notes when AgentCore Memory is unset |
| Gateway `WebSearch` | After deploy: search BIPs and public discussion |
| Etherscan MCP | Optional. Set `ETHERSCAN_API_KEY` for official EVM data + docs MCP |

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
[`.cursor/mcp.json`](../.cursor/mcp.json). Create a key at
https://etherscan.io/apidashboard and export it before starting Cursor or
the live agent:

```bash
export ETHERSCAN_API_KEY=your_key
```

| Server | URL | Auth |
| --- | --- | --- |
| `etherscan` | `https://mcp.etherscan.io/mcp` | `Authorization: Bearer $ETHERSCAN_API_KEY` |
| `etherscan-docs` | `https://docs.etherscan.io/mcp` | none |

BitcoinAgent attaches the same servers when `ETHERSCAN_API_KEY` is set
(docs-only: `ETHERSCAN_DOCS_MCP=1`). AgentCore Gateway cannot send an API
key to an MCP target, so the runtime talks to Etherscan directly. The
tools are read-only and count against your Etherscan quota.

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

- [AgentCore CLI](https://github.com/aws/agentcore-cli)
- [AgentCore CDK Constructs](https://github.com/aws/agentcore-l3-cdk-constructs)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
