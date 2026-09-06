"""Validate AgentCore invocation payloads before they reach the model."""

from __future__ import annotations

import re
from typing import Any

MAX_PROMPT_CHARS = 10_000
MAX_ACTOR_CHARS = 128
_ACTOR_RE = re.compile(r"^[A-Za-z0-9_.:@-]{1,128}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class PayloadError(ValueError):
    """Caller-facing validation error. Messages must not leak internals."""


def sanitize_text(value: str) -> str:
    cleaned = _CONTROL_CHARS.sub("", value)
    return " ".join(cleaned.split())


def validate_actor_id(actor_id: str) -> str:
    actor_id = actor_id.strip() or "default-user"
    if len(actor_id) > MAX_ACTOR_CHARS or not _ACTOR_RE.match(actor_id):
        raise PayloadError("Invalid userId. Use letters, numbers, and _.:@- only.")
    return actor_id


def extract_prompt(payload: dict) -> str | list:
    """Accept validated harness messages, tool results, or a plain prompt string."""
    if not isinstance(payload, dict):
        raise PayloadError("Request body must be a JSON object.")
    if "messages" in payload:
        return _strip_trailing_tool_use(payload["messages"])
    if "tool_results" in payload:
        tool_results = payload["tool_results"]
        if not isinstance(tool_results, list) or not all(
            isinstance(tool_result, dict) and isinstance(tool_result.get("toolUseId"), str)
            for tool_result in tool_results
        ):
            raise PayloadError("tool_results must contain objects with a toolUseId string.")
        return [{"role": "user", "content": [{"toolResult": {
            "toolUseId": tr["toolUseId"],
            "status": tr.get("status", "success"),
            "content": tr.get("content", []),
        }} for tr in tool_results]}]
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        raise PayloadError("Missing or invalid 'prompt' field.")
    prompt = sanitize_text(prompt)
    if not prompt:
        raise PayloadError("Missing or invalid 'prompt' field.")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise PayloadError(f"Prompt exceeds maximum length ({MAX_PROMPT_CHARS} characters).")
    return prompt


def _strip_trailing_tool_use(messages: Any) -> list[dict]:
    if not isinstance(messages, list):
        raise PayloadError("messages must be a list.")

    messages = list(messages)
    while messages:
        last = messages[-1]
        if not isinstance(last, dict):
            raise PayloadError("each message must be an object.")
        original_content = last.get("content", [])
        if not isinstance(original_content, list) or not all(isinstance(block, dict) for block in original_content):
            raise PayloadError("each message content value must be a list of content blocks.")

        content = [block for block in original_content if "toolUse" not in block]
        if len(content) == len(original_content):
            break
        if content:
            messages[-1] = {**last, "content": content}
            break
        messages.pop()

    return messages


# Kept as a public alias so existing tests and AgentCore notes still resolve.
strip_trailing_tool_use = _strip_trailing_tool_use
