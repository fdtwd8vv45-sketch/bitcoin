"""File-backed notes used when AgentCore Memory is not configured."""

from __future__ import annotations

from datetime import datetime, timezone

from agent_state import load_json, notes_path, reject_secrets, write_json
from optional_tool import tool


def _load_notes() -> list[dict[str, str]]:
    raw = load_json(notes_path(), [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and isinstance(item.get("text"), str)]


@tool
def remember_note(text: str) -> str:
    """Store a short local note about the user or this conversation.

    Use only when AgentCore Memory is unavailable. Never store seed phrases,
    private keys, or wallet passwords.
    """
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return "Provide a short note to remember."
    blocked = reject_secrets(cleaned)
    if blocked:
        return blocked
    if len(cleaned) > 500:
        return "Keep notes under 500 characters."
    notes = _load_notes()
    notes.append({"text": cleaned, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    write_json(notes_path(), notes[-50:])
    return f"Saved note ({len(notes[-50:])} stored locally)."


@tool
def recall_notes(query: str = "") -> str:
    """Recall locally stored notes, optionally filtered by a search phrase."""
    notes = _load_notes()
    if not notes:
        return "No local notes yet. Use remember_note or the local CLI `remember` command."
    needle = query.strip().lower()
    matched = [note for note in notes if not needle or needle in note["text"].lower()]
    if not matched:
        return f"No local notes match {query!r}."
    lines = [f"- {note['text']}" for note in matched[-20:]]
    return f"{len(matched)} local note(s):\n" + "\n".join(lines)
