# BitcoinAgent

A Strands agent on Amazon Bedrock AgentCore that answers Bitcoin Core questions
from this repository: JSON-RPC methods, docs, developer workflow, and public
chain status. After deploy it also remembers users and can search the web.

It was scaffolded with the [AgentCore CLI](https://github.com/aws/agentcore-cli)
(`Strands`, Bedrock, CodeZip) and then given memory, a gateway, evals, and
production hardening. See `PRODUCTION.md`.

## Tools

| Tool | Purpose |
| --- | --- |
| `lookup_rpc` | Explain a JSON-RPC method from the C++ source / bundled index |
| `list_rpc_methods` | List methods, optionally by category |
| `search_docs` | Search Bitcoin Core markdown docs |
| `developer_howto` | Short guides for `build`, `test`, `contribute`, `rpc`, `agent` |
| `recommended_fees` | Live fee estimates from mempool.space |
| `chain_tip_height` | Current Bitcoin tip height |
| `difficulty_adjustment` | Difficulty-adjustment estimate |
| `lookup_transaction` | Public tx lookup by 64-char hex txid |
| Gateway `WebSearch` | After deploy: search BIPs and public discussion |

## Memory, APIs, and production

- **Memory** `BitcoinMemory`: SEMANTIC + USER_PREFERENCE + SUMMARIZATION (30-day expiry). Env var `MEMORY_BITCOINMEMORY_ID` is injected after deploy. Use UUID session IDs (33+ chars). Not available in `agentcore dev`.
- **Gateway** `BitcoinGateway` (AWS_IAM + MCP) with a `WebSearch` connector. Env var `AGENTCORE_GATEWAY_BITCOINGATEWAY_URL` is injected after deploy.
- **Policy** `BitcoinPolicy` in LOG_ONLY. Attach Cedar from `policies/allow_read_tools.cedar.template` after the first deploy, then consider ENFORCE.
- **Evals** `BitcoinAccuracy` plus built-in Helpfulness, GoalSuccessRate, ToolSelectionAccuracy, Refusal. Online monitor `production_monitor` samples 5%. CI gate: `scripts/quality-gate.sh`.
- **App clients**: `clients/python/invoke_agent.py` and `clients/typescript/invoke_agent.ts` (IAM SigV4). Reuse one session id per conversation.
- **Hardening**: AWS_IAM inbound auth, prompt/userId validation, scoped IAM JSON, 900s idle / 2h max session, OTEL on.

Refresh the bundled index after RPC changes:

```bash
cd BitcoinAgent/app/BitcoinAgent
source .venv/bin/activate
python generate_rpc_index.py
python -m unittest discover -s tests
```

## Local development

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

The local server defaults to port **8080**. Memory and gateway URLs are not
available until you deploy.

## Deploy

```bash
cd BitcoinAgent
agentcore deploy
agentcore invoke "How do I run the functional tests?"
agentcore status
```

First deploy takes several minutes. This environment does not have AWS
credentials configured, so deploy is left for you to run.

# AgentCore Project

This project was created with the [AgentCore CLI](https://github.com/aws/agentcore-cli).

## Project Structure

```
my-project/
├── AGENTS.md               # AI coding assistant context
├── agentcore/
│   ├── agentcore.json      # Project config (agents, memories, credentials, gateways, evaluators)
│   ├── aws-targets.json    # Deployment targets (account + region)
│   ├── .env.local          # Secrets — API keys (gitignored)
│   ├── .llm-context/       # TypeScript type definitions for AI assistants
│   │   ├── agentcore.ts    # AgentCoreProjectSpec types
│   │   └── aws-targets.ts  # Deployment target types
│   └── cdk/                # CDK infrastructure (@aws/agentcore-cdk)
├── app/                    # Agent application code
└── evaluators/             # Custom evaluator code (if any)
```

## Getting Started

### Prerequisites

- **Node.js** 20.x or later
- **Python 3.10+** and **uv** for Python agents ([install uv](https://docs.astral.sh/uv/getting-started/installation/))
- **AWS credentials** configured (`aws configure` or environment variables)
- **Docker** (only for Container build agents)

### Development

Run your agent locally:

```bash
agentcore dev
```

### Validate Invocation Input

Validate runtime invocation payloads before forwarding them to an agent framework. Keep user prompts typed as strings
and pass only prompt text to the agent.

### Deployment

Deploy to AWS:

```bash
agentcore deploy
```

## Commands

| Command | Description |
| --- | --- |
| `agentcore create` | Create a new AgentCore project |
| `agentcore add` | Add resources (agent, memory, credential, gateway, evaluator, policy) |
| `agentcore remove` | Remove resources |
| `agentcore dev` | Run agent locally with hot-reload |
| `agentcore deploy` | Deploy to AWS via CDK |
| `agentcore status` | Show deployment status |
| `agentcore invoke` | Invoke agent (local or deployed) |
| `agentcore logs` | View agent logs |
| `agentcore traces` | View agent traces |
| `agentcore eval` | Run evaluations |
| `agentcore package` | Package agent artifacts |
| `agentcore validate` | Validate configuration |
| `agentcore pause` | Pause a deployed agent |
| `agentcore resume` | Resume a paused agent |
| `agentcore fetch` | Fetch remote resource definitions |
| `agentcore import` | Import existing resources |
| `agentcore update` | Check for CLI updates |

## Configuration

Edit the JSON files in `agentcore/` to configure your project. See `agentcore/.llm-context/` for type definitions and validation constraints.

The project uses a **flat resource model** — agents, memories, credentials, gateways, evaluators, and policies are top-level arrays in `agentcore.json`. Resources are independent; agents discover memories and credentials at runtime via environment variables or SDK calls.

## Resources

| Resource | Purpose |
| --- | --- |
| Agent (runtime) | HTTP, MCP, or A2A agent deployed to AgentCore Runtime |
| Memory | Persistent context storage with configurable strategies |
| Credential | API key or OAuth credential providers |
| Gateway | MCP gateway that routes tool calls to targets |
| Gateway Target | Tool implementation (Lambda, MCP server, OpenAPI, Smithy, API Gateway) |
| Evaluator | Custom LLM-as-a-Judge or code-based evaluation |
| Online Eval Config | Continuous evaluation pipeline for deployed agents |
| Policy | Cedar authorization policies for gateway tools |

### Agent Types

- **Template agents**: Created from framework templates (Strands, LangChain/LangGraph, GoogleADK, OpenAI Agents, Autogen)
- **BYO agents**: Bring your own code with `agentcore add agent --type byo`
- **Import agents**: Import existing Bedrock agents with `agentcore import`

### Build Types

- **CodeZip**: Python source packaged as a zip and deployed directly to AgentCore Runtime
- **Container**: Docker image built via CodeBuild (ARM64), pushed to ECR, and deployed to AgentCore Runtime

## Documentation

- [AgentCore CLI](https://github.com/aws/agentcore-cli)
- [AgentCore CDK Constructs](https://github.com/aws/agentcore-l3-cdk-constructs)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
