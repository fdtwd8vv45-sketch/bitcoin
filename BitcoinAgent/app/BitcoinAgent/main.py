from collections import OrderedDict
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager

from bitcoin_tools import developer_howto, list_rpc_methods, lookup_rpc, search_docs
from local_notes import recall_notes, remember_note
from mcp_client.client import get_gateway_mcp_client
from memory_session import MEMORY_ID, build_session_manager
from model.load import load_model
from network_tools import chain_tip_height, difficulty_adjustment, lookup_transaction, recommended_fees
from payload import PayloadError, extract_prompt, sanitize_text, strip_trailing_tool_use, validate_actor_id

app = BedrockAgentCoreApp()
log = app.logger

DEFAULT_SYSTEM_PROMPT = """
You are BitcoinAgent, a Bitcoin Core development assistant for this repository.

Help with JSON-RPC methods, build and test workflow, coding style, contributor
process, and public chain status (fees, tip height, difficulty, tx lookup).

Guidelines:
- Use lookup_rpc or list_rpc_methods for RPC questions
- Use search_docs for documentation and developer-notes questions
- Use developer_howto for common build/test/contribute/rpc/agent topics
- Use recommended_fees, chain_tip_height, difficulty_adjustment, or
  lookup_transaction for live public-network facts
- After deploy, BitcoinGateway may add web-search tools — use them for BIPs
  and recent public discussion, then verify against this repo when possible
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


def _tools_for_runtime() -> list:
    tools = list(LOCAL_TOOLS)
    gateway_client = get_gateway_mcp_client()
    if gateway_client:
        tools.append(gateway_client)
    return tools


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
