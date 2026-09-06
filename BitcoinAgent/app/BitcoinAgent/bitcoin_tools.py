"""Read-only Bitcoin Core helpers used by the BitcoinAgent tools."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from optional_tool import tool

_THIS_DIR = Path(__file__).resolve().parent
_INDEX_PATH = _THIS_DIR / "data" / "rpc_index.json"

# Wallet methods are often `RPCMethod name()` (no static). Helpers such as
# bumpfee_helper take arguments and are wired through one-line wrappers.
_RPC_METHOD_DEF = re.compile(r"(?:static\s+)?RPCMethod (\w+)\(([^)]*)\)\s*\{")
_RPC_WRAPPER = re.compile(r'RPCMethod (\w+)\(\)\s*\{\s*return (\w+)\("([^"]+)"\)')
_STRING_LIT = re.compile(r'"((?:[^"\\]|\\.)*)"')
_REGISTER = re.compile(r'\{\s*"([^"]+)"\s*,\s*&(\w+)\s*\}')


def repo_root() -> Path | None:
    """Return the Bitcoin Core checkout root, or None if it is not on disk."""
    env = os.environ.get("BITCOIN_REPO_ROOT")
    if env:
        candidate = Path(env).expanduser().resolve()
        if (candidate / "src" / "rpc").is_dir():
            return candidate

    for parent in _THIS_DIR.parents:
        if (parent / "src" / "rpc").is_dir() and (parent / "doc").is_dir():
            return parent
    return None


def _unescape_cpp_string(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")


def _extract_rpc_methods(source: str, relpath: str) -> tuple[dict[str, dict], dict[str, dict]]:
    methods: dict[str, dict] = {}
    helpers: dict[str, dict] = {}
    for match in _RPC_METHOD_DEF.finditer(source):
        fn_name = match.group(1)
        params = match.group(2).strip()
        chunk = source[match.end() : match.end() + 6000]
        method_start = chunk.find("return RPCMethod{")
        if method_start < 0:
            continue
        after = chunk[method_start + len("return RPCMethod{") :].lstrip()
        literals = _STRING_LIT.findall(chunk[method_start:])
        if params:
            if literals:
                helpers[fn_name] = {
                    "description": _unescape_cpp_string(literals[0]).strip(),
                    "source": relpath,
                    "function": fn_name,
                }
            continue
        if not after.startswith('"') or len(literals) < 2:
            continue
        name = _unescape_cpp_string(literals[0])
        description = _unescape_cpp_string(literals[1]).strip()
        methods[name] = {
            "name": name,
            "function": fn_name,
            "description": description,
            "source": relpath,
            "category": "",
        }

    for match in _RPC_WRAPPER.finditer(source):
        wrapper_fn, helper_fn, rpc_name = match.group(1), match.group(2), match.group(3)
        if rpc_name in methods:
            continue
        template = helpers.get(helper_fn, {})
        methods[rpc_name] = {
            "name": rpc_name,
            "function": wrapper_fn,
            "description": template.get("description") or f"See {helper_fn} in {relpath}.",
            "source": relpath,
            "category": "",
        }
    return methods, helpers


def _extract_categories(source: str) -> dict[str, str]:
    """Map C++ function name -> RPC category from CRPCCommand tables."""
    return {fn: category for category, fn in _REGISTER.findall(source)}


def build_rpc_index(root: Path | None = None) -> dict[str, dict]:
    """Scan Bitcoin Core C++ sources and return an RPC method index."""
    root = root or repo_root()
    if root is None:
        raise FileNotFoundError("Bitcoin Core repository root was not found")

    index: dict[str, dict] = {}
    categories: dict[str, str] = {}
    for path in sorted((root / "src").rglob("*.cpp")):
        text = path.read_text(encoding="utf-8", errors="replace")
        relpath = str(path.relative_to(root))
        categories.update(_extract_categories(text))
        methods, _helpers = _extract_rpc_methods(text, relpath)
        index.update(methods)

    for name, entry in index.items():
        entry["category"] = categories.get(entry["function"], "") or categories.get(name, "")
    return dict(sorted(index.items()))


def write_rpc_index(root: Path | None = None, dest: Path | None = None) -> Path:
    dest = dest or _INDEX_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(build_rpc_index(root), indent=2) + "\n", encoding="utf-8")
    return dest


@lru_cache(maxsize=1)
def load_rpc_index() -> dict[str, dict]:
    if _INDEX_PATH.is_file():
        return json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    root = repo_root()
    if root is not None:
        return build_rpc_index(root)
    return {}


@tool
def lookup_rpc(name: str) -> str:
    """Look up a Bitcoin Core JSON-RPC method by name.

    Use this when the user asks what an RPC does, which arguments it takes,
    or where it is implemented. The name is matched case-insensitively.
    """
    needle = name.strip().lstrip("/")
    if not needle:
        return "Provide an RPC method name such as getblockcount."

    index = load_rpc_index()
    exact = index.get(needle) or index.get(needle.lower())
    if exact:
        return _format_rpc(exact)

    matches = [
        entry
        for key, entry in index.items()
        if needle.lower() in key.lower()
    ]
    if not matches:
        return f"No RPC method matching {needle!r} was found in this Bitcoin Core tree."
    if len(matches) == 1:
        return _format_rpc(matches[0])

    lines = [f"Multiple RPC methods match {needle!r}:"]
    for entry in matches[:20]:
        category = entry.get("category") or "unknown"
        lines.append(f"- {entry['name']} ({category})")
    if len(matches) > 20:
        lines.append(f"... and {len(matches) - 20} more")
    return "\n".join(lines)


@tool
def list_rpc_methods(category: str = "") -> str:
    """List Bitcoin Core JSON-RPC methods, optionally filtered by category.

    Categories include blockchain, control, mining, net, rawtransactions,
    util, wallet, and hidden.
    """
    index = load_rpc_index()
    if not index:
        return "The RPC index is empty. Run generate_rpc_index.py from a Bitcoin Core checkout."

    wanted = category.strip().lower()
    rows = []
    for entry in index.values():
        entry_category = (entry.get("category") or "unknown").lower()
        if wanted and wanted not in (entry_category, entry["name"].lower()):
            continue
        rows.append(f"- {entry['name']} ({entry.get('category') or 'unknown'}): {entry['description'].splitlines()[0]}")

    if not rows:
        available = sorted({entry.get("category") or "unknown" for entry in index.values()})
        return (
            f"No RPC methods found for category {category!r}. "
            f"Known categories: {', '.join(available)}"
        )
    header = f"{len(rows)} RPC method(s)"
    if wanted:
        header += f" in category {wanted!r}"
    return header + ":\n" + "\n".join(rows)


@tool
def search_docs(query: str) -> str:
    """Search Bitcoin Core markdown documentation for a topic.

    Use this for build instructions, developer notes, RPC interface docs,
    testing, and contribution workflow questions.
    """
    q = query.strip()
    if not q:
        return "Provide a search query such as 'functional tests' or 'JSON-RPC'."

    root = repo_root()
    terms = [part.lower() for part in re.split(r"\s+", q) if part]
    hits: list[tuple[int, str, str]] = []

    bundled = _THIS_DIR / "data" / "doc_snippets.json"
    docs: list[tuple[str, str]] = []
    if root is not None:
        for path in sorted((root / "doc").rglob("*.md")):
            docs.append((str(path.relative_to(root)), path.read_text(encoding="utf-8", errors="replace")))
    elif bundled.is_file():
        for item in json.loads(bundled.read_text(encoding="utf-8")):
            docs.append((item["path"], item["text"]))

    if not docs:
        return "Documentation is not available in this environment."

    for relpath, text in docs:
        score = 0
        lowered = text.lower()
        for term in terms:
            score += lowered.count(term)
            if term in relpath.lower():
                score += 5
        if score == 0:
            continue
        excerpt = _best_excerpt(text, terms)
        hits.append((score, relpath, excerpt))

    hits.sort(key=lambda item: item[0], reverse=True)
    if not hits:
        return f"No documentation matches {q!r}."

    blocks = []
    for score, relpath, excerpt in hits[:6]:
        blocks.append(f"## {relpath}\n{excerpt}")
    return "\n\n".join(blocks)


@tool
def developer_howto(topic: str) -> str:
    """Return a short Bitcoin Core developer how-to for a common topic.

    Supported topics: build, test, contribute, rpc, agent, local.
    """
    key = topic.strip().lower()
    guides = {
        "build": (
            "Configure and build from the repository root with CMake:\n"
            "1. Install dependencies for your OS (see doc/dependencies.md and doc/build-*.md).\n"
            "2. cmake -B build\n"
            "3. cmake --build build -j$(nproc)\n"
            "The GUI is optional; pass -DBUILD_GUI=ON if you need bitcoin-qt."
        ),
        "test": (
            "Unit tests: from the build directory run `ctest`.\n"
            "Functional tests: `build/test/functional/test_runner.py` "
            "(see /test and src/test/README.md).\n"
            "Add unit tests for new C++ code and a test plan on risky changes."
        ),
        "contribute": (
            "Follow CONTRIBUTING.md: small, reviewable patches; tests for new behavior; "
            "no drive-by style-only changes. Use the coding style in doc/developer-notes.md "
            "and src/.clang-format. Translations go through Transifex, not GitHub PRs."
        ),
        "rpc": (
            "bitcoind exposes JSON-RPC on `/` and `/wallet/<walletname>/`. "
            "Use bitcoin-cli or curl with JSON-RPC 2.0. See doc/JSON-RPC-interface.md. "
            "Call lookup_rpc or list_rpc_methods for method-specific help from this tree."
        ),
        "agent": (
            "This AgentCore project lives in BitcoinAgent/. "
            "No AWS: `python3 BitcoinAgent/app/BitcoinAgent/local_cli.py "
            "\"What does getblockcount do?\"` or `./BitcoinAgent/scripts/doctor.sh`. "
            "With AWS: `cd BitcoinAgent && agentcore dev` then "
            "`agentcore invoke --dev \"What does getblockcount do?\"`. "
            "Deploy: `agentcore deploy` then `./scripts/after_deploy.sh`."
        ),
        "local": (
            "Use the tools without Bedrock or AWS:\n"
            "1. python3 BitcoinAgent/app/BitcoinAgent/local_cli.py\n"
            "2. Commands: rpc, list, docs, howto, fees, tip, tx, remember, notes\n"
            "3. ./BitcoinAgent/scripts/doctor.sh explains what is still needed "
            "for agentcore dev / deploy."
        ),
    }
    if key in guides:
        return guides[key]
    return (
        "Unknown topic. Use one of: build, test, contribute, rpc, agent, local.\n"
        "You can also call search_docs with a free-text query."
    )


def _format_rpc(entry: dict) -> str:
    lines = [
        f"RPC: {entry['name']}",
        f"Category: {entry.get('category') or 'unknown'}",
        f"Source: {entry.get('source') or 'unknown'}",
        "",
        entry.get("description") or "No description extracted.",
    ]
    return "\n".join(lines)


def _best_excerpt(text: str, terms: list[str], radius: int = 240) -> str:
    lowered = text.lower()
    positions = [lowered.find(term) for term in terms if term in lowered]
    if not positions:
        return text[: radius * 2].strip()
    pos = min(positions)
    start = max(0, pos - radius)
    end = min(len(text), pos + radius)
    excerpt = text[start:end].strip()
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."
    return excerpt
