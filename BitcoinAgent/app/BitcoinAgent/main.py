from collections import OrderedDict
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager

from agentic_wallet import agentic_wallet_overview, agentic_wallet_status
from apko_smoke import (
    apko_docker_status,
    apko_plan_smoke,
    apko_smoke_overview,
    apko_smoke_preflight,
    apko_smoke_run,
)
from bitcoin_tools import developer_howto, list_rpc_methods, lookup_rpc, search_docs
from contract_source import lookup_contract_source
from jupiter import (
    jupiter_cli_status,
    jupiter_overview,
    jupiter_price,
    jupiter_token_search,
    jupiter_verify_eligibility,
)
from phantom_connect import (
    phantom_connect_cli_status,
    phantom_connect_overview,
    phantom_connect_packages,
)
from coinstats import (
    coinstats_coin,
    coinstats_markets,
    coinstats_overview,
    coinstats_portfolio,
    coinstats_portfolio_list,
    coinstats_status,
    coinstats_wallet,
)
from cubic import cubic_overview, cubic_status
from libbndl import (
    libbndl_add,
    libbndl_create,
    libbndl_extract,
    libbndl_fetch,
    libbndl_inspect,
    libbndl_lookup,
    libbndl_overview,
    libbndl_replace,
    libbndl_types,
)
from execution_apis import (
    execution_apis_contribute,
    execution_apis_graphql,
    execution_apis_list,
    execution_apis_method,
    execution_apis_overview,
)
from etherscan_stats import (
    etherscan_eth_price,
    etherscan_eth_supply,
    etherscan_gas_oracle,
    etherscan_node_count,
    etherscan_stats,
    etherscan_stats_overview,
    etherscan_stats_status,
)
from local_notes import recall_notes, remember_note
from mcp_client.client import (
    get_etherscan_docs_mcp_client,
    get_etherscan_mcp_client,
    get_gateway_mcp_client,
    get_jupiter_docs_mcp_client,
    get_phantom_docs_mcp_client,
)
from memory_session import MEMORY_ID, build_session_manager
from model.load import load_model
from network_tools import chain_tip_height, difficulty_adjustment, lookup_address, lookup_transaction, recommended_fees
from receive_check import check_receive
from payload import PayloadError, extract_prompt, sanitize_text, strip_trailing_tool_use, validate_actor_id

app = BedrockAgentCoreApp()
log = app.logger

DEFAULT_SYSTEM_PROMPT = """
You are BitcoinAgent, a Bitcoin Core development assistant for this repository.

Help with JSON-RPC methods, build and test workflow, coding style, contributor
process, and public chain status (fees, tip height, difficulty, tx lookup).
If someone thinks they did not receive bitcoin, help them tell a delay
from a real mistake using check_receive. Never ask for secrets.

Guidelines:
- Use lookup_rpc or list_rpc_methods for RPC questions
- Use search_docs for documentation and developer-notes questions
- Use developer_howto for common build/test/contribute/rpc/agent/local/receive/wallet/agentic/jupiter/phantom/coinstats/cubic/libbndl/apko/execution/etherscan-stats topics
- Use check_receive when the user is waiting on a payment or worries they
  copied the wrong address. Prefer an address or txid; never a seed phrase
- Use recommended_fees, chain_tip_height, difficulty_adjustment,
  lookup_transaction, or lookup_address for live public-network facts
- Use lookup_contract_source for verified EVM contract source, ABI, and
  compiler settings (Etherscan getsourcecode). Needs ETHERSCAN_API_KEY.
  If the address is a proxy, fetch the implementation too. Do not run the
  source. If it is unverified, say so instead of guessing.
- After deploy, BitcoinGateway may add web-search tools — use them for BIPs
  and recent public discussion, then verify against this repo when possible
- If Etherscan MCP is attached, use it only for public EVM-chain lookups
  (balances, transactions, contracts, gas) that lookup_contract_source
  and etherscan_stats_* do not cover. It is read-only and counts against
  the Etherscan API quota. Prefer repo tools for Bitcoin questions.
- If Etherscan docs MCP is attached, use it for Etherscan API/docs questions
- Use agentic_wallet_overview for OKX Agentic Wallet (TEE keys, email/Google/Apple
  login, x402). Use agentic_wallet_status to see if the onchainos CLI is installed
  or logged in. Do not send, swap, trade, or sign through this agent. Never store
  OTP codes, API keys, or seed phrases.
- Use jupiter_overview for Jupiter APIs and AI tools (llms.txt, skills, docs MCP,
  CLI). Use jupiter_price for USD prices and jupiter_token_search for Solana token
  metadata. Use jupiter_verify_eligibility to check Jupiter VRFD Express
  eligibility (read-only GET). Use jupiter_cli_status to see if the official
  `jup` CLI is installed. If Jupiter docs MCP is attached, use it for Jupiter
  API/docs questions. Do not swap, place orders, lend, sign, craft Express
  payment transactions, or POST /execute through this agent.
- Use phantom_connect_overview for Phantom Connect SDKs (React, Browser, React
  Native), Portal App ID, and docs MCP. Use phantom_connect_packages for npm
  latest versions and phantom_connect_cli_status for `phantom --version`. If
  Phantom docs MCP is attached, use it for Phantom SDK/docs questions. Do not
  connect a wallet, login, sign, send, swap, or attach @phantom/mcp-server
  through this agent.
- Use coinstats_overview for the CoinStats hosted MCP
  (mcp.coinstats.app, OAuth in Cursor). Use coinstats_coin / coinstats_markets
  for prices and global market cap, coinstats_portfolio_list /
  coinstats_portfolio for your portfolios + PnL, coinstats_wallet for a
  public wallet balance on one chain, and coinstats_status to see if
  COINSTATS_API_KEY is set (never print it). Needs the key for REST. Do not
  add transactions, connect wallets/exchanges, sync, or delete portfolios.
  Do not attach the hosted CoinStats MCP write tools through this agent.
- Use cubic_overview for the cubic hosted MCP (www.cubic.dev/api/mcp,
  OAuth in Cursor). Use cubic_status to see if CUBIC_API_KEY is set
  (never print it) and whether the cubic CLI is on PATH. Do not attach
  the hosted cubic MCP. Do not start reviews, change issue state, update
  seats or subscriptions, or upload repository secrets through this agent.
- Use libbndl_overview for Criterion/EA BUNDLE archives (libbndl pinned to
  Bo98/libbndl@2b88eff, non-Xbox BNDL + v3/v4). Use libbndl_inspect /
  libbndl_types / libbndl_lookup to list resources, libbndl_extract to write
  GetBinary payloads, libbndl_create / libbndl_add / libbndl_replace to Save
  BND2 PC archives, and libbndl_fetch to download an http(s) archive. Do not
  execute extracted payloads.
- Use apko_smoke_overview for the APKO smoke-test pin
  (ethereum-optimism/actions@7eaff21e → factory@b87283a8). Use
  apko_plan_smoke to plan catalog smoke legs (amd64 → ubuntu-24.04, not
  ubuntu-slim). Use apko_docker_status / apko_smoke_preflight /
  apko_smoke_run to require a Docker daemon, pull the image, and check
  architecture before the command loop. Do not publish images or log in
  to Artifact Registry through this agent.
- Use execution_apis_overview for the Ethereum Execution APIs OpenRPC
  spec (ethereum/execution-apis@34151926). Use execution_apis_method /
  execution_apis_list for JSON-RPC methods (eth, engine, debug, txpool,
  net, testing), execution_apis_graphql for EIP-1767 fields, and
  execution_apis_contribute for make build / Docusaurus / hive rpc-compat.
  Spec only. Do not connect to an execution client, send transactions,
  sign, or call engine_* / testing_commitBlockV1 through this agent.
- Use etherscan_stats_overview for Etherscan charts/stats
  (etherscan.io/charts). Use etherscan_stats for a free-tier snapshot
  (ethsupply2 + ethprice + nodecount + gasoracle), etherscan_eth_supply /
  etherscan_eth_price / etherscan_node_count / etherscan_gas_oracle for
  one metric, and etherscan_stats_status to see if ETHERSCAN_API_KEY is
  set (never print it). Do not call PRO daily-chart endpoints
  (dailytx, dailynewaddress, …) or send transactions through this agent.
- Remember user preferences and facts when AgentCore Memory is available
- When memory is not available, use remember_note / recall_notes for short
  local notes (never store secrets)
- Be concise and precise
- If a tool returns no match, say so instead of inventing Bitcoin Core behavior
- Do not give advice that would help steal funds, attack the network, or
  bypass wallet/security controls
- Never ask for or handle seed phrases, private keys, or wallet passwords
"""

LOCAL_TOOLS = [
    lookup_rpc,
    list_rpc_methods,
    search_docs,
    developer_howto,
    recommended_fees,
    chain_tip_height,
    difficulty_adjustment,
    lookup_transaction,
    lookup_address,
    lookup_contract_source,
    check_receive,
    agentic_wallet_overview,
    agentic_wallet_status,
    jupiter_overview,
    jupiter_price,
    jupiter_token_search,
    jupiter_verify_eligibility,
    jupiter_cli_status,
    phantom_connect_overview,
    phantom_connect_packages,
    phantom_connect_cli_status,
    coinstats_overview,
    coinstats_coin,
    coinstats_markets,
    coinstats_portfolio_list,
    coinstats_portfolio,
    coinstats_wallet,
    coinstats_status,
    cubic_overview,
    cubic_status,
    libbndl_overview,
    libbndl_inspect,
    libbndl_lookup,
    libbndl_types,
    libbndl_extract,
    libbndl_create,
    libbndl_add,
    libbndl_replace,
    libbndl_fetch,
    apko_smoke_overview,
    apko_plan_smoke,
    apko_docker_status,
    apko_smoke_preflight,
    apko_smoke_run,
    execution_apis_overview,
    execution_apis_method,
    execution_apis_list,
    execution_apis_graphql,
    execution_apis_contribute,
    etherscan_stats_overview,
    etherscan_stats,
    etherscan_eth_supply,
    etherscan_eth_price,
    etherscan_node_count,
    etherscan_gas_oracle,
    etherscan_stats_status,
]
if not MEMORY_ID:
    LOCAL_TOOLS.extend([remember_note, recall_notes])

_INLINE_FUNCTION_NAMES = {tool_fn.__name__ for tool_fn in LOCAL_TOOLS}


def _header_map(context: Any) -> dict[str, str]:
    headers = getattr(context, "request_headers", None) or getattr(context, "headers", None) or {}
    if not isinstance(headers, dict):
        return {}
    return {str(key): str(value) for key, value in headers.items()}


def _actor_id(payload: dict, context: Any) -> str:
    headers = _header_map(context)
    raw = (
        payload.get("userId")
        or headers.get("X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId")
        or "default-user"
    )
    if not isinstance(raw, str):
        raise PayloadError("Invalid userId.")
    return validate_actor_id(sanitize_text(raw))


def _optional_mcp_clients() -> list:
    clients = []
    for factory in (
        get_gateway_mcp_client,
        get_etherscan_mcp_client,
        get_etherscan_docs_mcp_client,
        get_jupiter_docs_mcp_client,
        get_phantom_docs_mcp_client,
    ):
        client = factory()
        if client:
            clients.append(client)
    return clients


def _tools_for_runtime() -> list:
    return [*LOCAL_TOOLS, *_optional_mcp_clients()]


def _make_conversation_manager():
    return NullConversationManager()


def agent_factory():
    cache: OrderedDict[tuple[str, str], Agent] = OrderedDict()

    def get_or_create_agent(session_id: str, actor_id: str) -> Agent:
        key = (actor_id, session_id)
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        if len(cache) >= 128:
            cache.popitem(last=False)
        session_manager = build_session_manager(actor_id, session_id)
        kwargs: dict[str, Any] = {
            "model": load_model(),
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "tools": _tools_for_runtime(),
            "hooks": [],
        }
        if session_manager is not None:
            kwargs["session_manager"] = session_manager
        else:
            kwargs["conversation_manager"] = _make_conversation_manager()
        cache[key] = Agent(**kwargs)
        return cache[key]

    return get_or_create_agent


get_or_create_agent = agent_factory()


def _has_inline_function_call(messages) -> bool:
    if not _INLINE_FUNCTION_NAMES or not isinstance(messages, list):
        return False
    for msg in messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("toolUse", {}).get("name") in _INLINE_FUNCTION_NAMES:
                    return True
    return False


def _is_inline_function_call(event: dict) -> bool:
    if not _INLINE_FUNCTION_NAMES:
        return False
    cbs = event.get("contentBlockStart", {})
    start = cbs.get("start", {})
    tool_use = start.get("toolUse") if isinstance(start, dict) else None
    return tool_use is not None and tool_use.get("name") in _INLINE_FUNCTION_NAMES


@app.entrypoint
async def invoke(payload, context):
    try:
        if not isinstance(payload, dict):
            yield {"error": "Request body must be a JSON object."}
            return
        actor_id = _actor_id(payload, context)
        session_id = getattr(context, "session_id", None) or payload.get("sessionId") or "default-session"
        if not isinstance(session_id, str) or not session_id.strip():
            yield {"error": "Invalid sessionId."}
            return
        if MEMORY_ID and len(session_id) < 33:
            log.warning("Session id %r is shorter than 33 characters; long-term memory extraction may fail.", session_id)
        prompt = extract_prompt(payload)
        agent = get_or_create_agent(session_id, actor_id)
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict) or "event" not in event:
                continue
            cbs = event["event"].get("contentBlockStart")
            if cbs is not None and not cbs.get("start"):
                continue
            yield event
    except PayloadError as exc:
        yield {"error": str(exc)}
    except Exception as exc:
        log.error("Agent error: %s", exc, exc_info=True)
        yield {"error": "An error occurred. Please try again."}


if __name__ == "__main__":
    app.run()
