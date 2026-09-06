#!/usr/bin/env python3
"""Build the bundled Bitcoin Core RPC index used by bitcoin_tools."""

from __future__ import annotations

import json
from pathlib import Path

from bitcoin_tools import repo_root, write_rpc_index

DOC_SNIPPET_FILES = [
    "doc/JSON-RPC-interface.md",
    "doc/developer-notes.md",
    "CONTRIBUTING.md",
    "README.md",
    "INSTALL.md",
]


def write_doc_snippets(root: Path, dest: Path) -> None:
    snippets = []
    for relpath in DOC_SNIPPET_FILES:
        path = root / relpath
        if path.is_file():
            snippets.append({"path": relpath, "text": path.read_text(encoding="utf-8", errors="replace")[:20000]})
    dest.write_text(json.dumps(snippets, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    root = repo_root()
    if root is None:
        raise SystemExit("Bitcoin Core repository root was not found")
    dest = write_rpc_index(root)
    write_doc_snippets(root, dest.parent / "doc_snippets.json")
    print(f"Wrote {dest}")


if __name__ == "__main__":
    main()
