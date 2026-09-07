"""Local files for session reuse and notes (no AWS required)."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

_SECRET_RE = re.compile(
    r"\b(seed phrase|mnemonic|private key|wif|xprv|xpub|wallet password)\b",
    re.IGNORECASE,
)


def agent_home() -> Path:
    env = os.environ.get("BITCOIN_AGENT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".bitcoin-agent"


def session_path() -> Path:
    return agent_home() / "session.json"


def notes_path() -> Path:
    return agent_home() / "notes.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def load_or_create_session(*, new_session: bool = False, user_id: str | None = None) -> dict[str, str]:
    data = {} if new_session else load_json(session_path(), {})
    if not isinstance(data, dict):
        data = {}
    session_id = data.get("sessionId") if isinstance(data.get("sessionId"), str) else ""
    if new_session or len(session_id) < 33:
        session_id = str(uuid.uuid4())
    resolved_user = user_id or (data.get("userId") if isinstance(data.get("userId"), str) else None) or "default-user"
    record = {"sessionId": session_id, "userId": resolved_user}
    write_json(session_path(), record)
    return record


def reject_secrets(text: str) -> str | None:
    if _SECRET_RE.search(text):
        return "Refusing to store seed phrases, private keys, or wallet passwords."
    return None
