"""Read-only Ethereum Execution APIs spec lookup (JSON-RPC OpenRPC + GraphQL).

Pinned to ethereum/execution-apis@34151926. This module never talks to an
execution client, never sends engine payloads, and never signs or
broadcasts transactions.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from optional_tool import tool

SPEC_COMMIT = "34151926fbf395e66797add1f60fd759681678e6"
SPEC_VERSION = "1.0.0-beta.7"
GITHUB_URL = "https://github.com/ethereum/execution-apis"
TREE_URL = f"{GITHUB_URL}/tree/{SPEC_COMMIT}"
COMMIT_URL = f"{GITHUB_URL}/commit/{SPEC_COMMIT}"
DOCS_URL = "https://ethereum.github.io/execution-apis/"
QUICKSTART_URL = "https://ethereum.github.io/execution-apis/docs/quickstart/"
CONTRIBUTING_URL = f"{GITHUB_URL}/blob/{SPEC_COMMIT}/CONTRIBUTING.md"
CONTRIBUTORS_GUIDE_URL = (
    f"{GITHUB_URL}/blob/{SPEC_COMMIT}/docs-api/docs/contributors-guide.md"
)
TESTS_DOC_URL = f"{GITHUB_URL}/blob/{SPEC_COMMIT}/docs-api/docs/tests.md"
ENGINE_AUTH_URL = f"{GITHUB_URL}/blob/{SPEC_COMMIT}/src/engine/authentication.md"
GRAPHQL_SCHEMA_URL = f"{GITHUB_URL}/blob/{SPEC_COMMIT}/schema.graphqls"
OPENRPC_URL = "https://open-rpc.org"
EIP_1767_URL = "https://eips.ethereum.org/EIPS/eip-1767"
HIVE_RPC_COMPAT_URL = (
    "https://github.com/ethereum/hive/tree/master/simulators/ethereum/rpc-compat"
)
HIVE_RESULTS_URL = "https://hive.ethpandaops.io"
NAMESPACES = ("eth", "engine", "debug", "txpool", "net", "testing")
_WRITE_EXACT = {
    "eth_sendTransaction",
    "eth_sendRawTransaction",
    "eth_sign",
    "eth_signTransaction",
    "eth_fillTransaction",
    "testing_commitBlockV1",
}
_THIS_DIR = Path(__file__).resolve().parent
_INDEX_PATH = _THIS_DIR / "data" / "execution_apis_index.json"
_METHOD_TOKEN = re.compile(
    r"\b((?:eth|engine|debug|txpool|net|testing|web3)_[A-Za-z0-9]+)\b",
    re.I,
)
_SECRET_TOKENS = (
    "seed",
    "xprv",
    "private",
    "secret key",
    "api key",
    "recovery phrase",
    "jwt secret",
    "jwt-secret",
)


def _secret_query(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _SECRET_TOKENS)


def classify_method(name: str) -> str:
    """Return read, write, engine, or testing. Never implies a live RPC call."""
    prefix = name.split("_", 1)[0]
    if prefix == "engine":
        return "engine"
    if prefix == "testing":
        return "testing"
    if name in _WRITE_EXACT:
        return "write"
    return "read"


def schema_label(schema: Any) -> str:
    """Turn an OpenRPC/JSON Schema fragment into a short type label."""
    if not isinstance(schema, dict):
        return ""
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref:
        return ref.rsplit("/", 1)[-1]
    if "oneOf" in schema and isinstance(schema["oneOf"], list):
        parts = [schema_label(item) for item in schema["oneOf"]]
        parts = [part for part in parts if part]
        return " | ".join(parts) if parts else "oneOf"
    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        parts = [schema_label(item) for item in schema["anyOf"]]
        parts = [part for part in parts if part]
        return " | ".join(parts) if parts else "anyOf"
    schema_type = schema.get("type")
    if schema_type == "array":
        items = schema_label(schema.get("items"))
        return f"array[{items}]" if items else "array"
    if schema_type == "object":
        title = schema.get("title")
        return str(title) if title else "object"
    if isinstance(schema_type, str):
        return schema_type
    title = schema.get("title")
    return str(title) if title else ""


@lru_cache(maxsize=1)
def load_index() -> dict[str, Any]:
    if not _INDEX_PATH.is_file():
        return {}
    payload = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_methods() -> dict[str, dict[str, Any]]:
    methods = load_index().get("methods") or {}
    return methods if isinstance(methods, dict) else {}


def method_namespaces() -> list[str]:
    found = {str(entry.get("namespace") or "") for entry in load_methods().values()}
    ordered = [name for name in NAMESPACES if name in found]
    extras = sorted(name for name in found if name and name not in NAMESPACES)
    return ordered + extras


def _kind_banner(kind: str) -> str:
    if kind == "write":
        return (
            "Kind: write (sign / send / fill). Spec only — this agent will not "
            "call an execution client or move funds."
        )
    if kind == "engine":
        return (
            "Kind: engine (EL ↔ CL, JWT on port 8551). Spec only — this agent "
            "will not send forkchoice, newPayload, or getPayload messages."
        )
    if kind == "testing":
        return (
            "Kind: testing (hive / rpctestgen helpers). Spec only — this agent "
            "will not build or commit blocks on a node."
        )
    return "Kind: read. Spec only — this agent will not call an execution client."


def _format_param(param: dict[str, Any]) -> str:
    name = param.get("name") or "param"
    required = "required" if param.get("required") else "optional"
    schema = param.get("schema") or ""
    line = f"- {name} ({required}"
    if schema:
        line += f", {schema}"
    line += ")"
    enum_values = param.get("enum") or []
    if enum_values:
        line += ": " + ", ".join(str(v) for v in enum_values)
    return line


def format_method(entry: dict[str, Any]) -> str:
    name = entry.get("name") or "unknown"
    lines = [
        f"Execution API: {name}",
        f"Namespace: {entry.get('namespace') or 'unknown'}",
        _kind_banner(str(entry.get("kind") or "read")),
        f"Source: {GITHUB_URL}/blob/{SPEC_COMMIT}/{entry.get('source') or ''}",
        "",
        entry.get("summary") or "No summary in the bundled spec.",
    ]
    description = (entry.get("description") or "").strip()
    if description:
        lines.extend(["", description])
    params = entry.get("params") or []
    lines.extend(["", "Params:"])
    if params:
        lines.extend(_format_param(p) for p in params if isinstance(p, dict))
    else:
        lines.append("- none")
    result_name = entry.get("result_name") or "Result"
    result_schema = entry.get("result_schema") or ""
    result_line = f"Result: {result_name}"
    if result_schema:
        result_line += f" ({result_schema})"
    lines.extend(["", result_line])
    docs_url = entry.get("external_docs_url") or ""
    if docs_url:
        extra = entry.get("external_docs") or "external docs"
        lines.append(f"External: {extra} — {docs_url}")
    errors = entry.get("errors") or []
    if errors:
        lines.append("Errors: " + "; ".join(str(e) for e in errors))
    groups = entry.get("error_groups") or []
    if groups:
        lines.append("Error groups: " + ", ".join(str(g) for g in groups))
    examples = entry.get("examples") or []
    if examples and isinstance(examples[0], dict):
        example = examples[0]
        lines.extend(["", f"Example: {example.get('name') or name}"])
        for param in example.get("params") or []:
            if not isinstance(param, dict):
                continue
            lines.append(f"  {param.get('name') or 'param'} = {param.get('value')}")
        if example.get("result"):
            lines.append(f"  → {example['result']}")
    lines.extend(
        [
            "",
            "This is the OpenRPC spec, not a live node. Use an execution client "
            "on a machine you control if you need to actually call the method.",
            f"Docs: {DOCS_URL}",
        ]
    )
    return "\n".join(lines)


def resolve_methods(query: str) -> tuple[list[dict[str, Any]], str]:
    """Match a user query onto bundled methods. Empty query means no match."""
    raw = (query or "").strip()
    if not raw:
        return [], ""
    methods = load_methods()
    if not methods:
        return [], "empty"
    lowered = raw.lower().replace("-", "_")
    token_match = _METHOD_TOKEN.search(raw)
    if token_match:
        lowered = token_match.group(1).lower()
    exact = methods.get(lowered)
    if not exact:
        for key, entry in methods.items():
            if key.lower() == lowered:
                exact = entry
                break
    if exact:
        return [exact], "exact"
    suffix_hits = [
        entry
        for key, entry in methods.items()
        if key.lower().split("_", 1)[-1] == lowered
    ]
    if suffix_hits:
        return suffix_hits, "suffix"
    prefix_hits = [
        entry
        for key, entry in methods.items()
        if key.lower().startswith(lowered + "_") or key.lower().startswith(lowered)
    ]
    if len(prefix_hits) == 1:
        return prefix_hits, "prefix"
    contains = [
        entry
        for key, entry in methods.items()
        if lowered in key.lower() or lowered in str(entry.get("summary") or "").lower()
    ]
    return contains, "contains"


def _overview_text() -> str:
    methods = load_methods()
    namespaces = method_namespaces()
    counts = []
    for namespace in namespaces:
        n = sum(1 for entry in methods.values() if entry.get("namespace") == namespace)
        counts.append(f"{namespace} ({n})")
    return (
        "Ethereum Execution APIs are the canonical JSON-RPC methods every "
        "execution client implements, so wallets and tooling can treat Geth, "
        "Nethermind, Besu, Erigon, and others as interchangeable modules.\n"
        "\n"
        f"Published docs: {DOCS_URL}  (OpenRPC version {SPEC_VERSION})\n"
        f"Quickstart / contributing: {QUICKSTART_URL}\n"
        f"Source: {GITHUB_URL}\n"
        f"Bundled pin: {COMMIT_URL}\n"
        f"  ({SPEC_COMMIT[:12]} — EIP-1898 block objects in "
        f"BlockNumberOrTagOrHash, on top of {SPEC_VERSION})\n"
        "\n"
        "JSON-RPC is written as OpenRPC YAML under src/eth, src/engine, "
        "src/debug, src/txpool, and src/testing. `make build` compiles it to "
        "a single openrpc.json with $refs resolved. GraphQL (EIP-1767) lives "
        f"in schema.graphqls / graphql.json ({EIP_1767_URL}).\n"
        "\n"
        f"Bundled methods ({len(methods)}): " + ", ".join(counts) + ".\n"
        "\n"
        "Read the spec from this agent:\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution "
        "eth_blockNumber\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution list eth\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution graphql\n"
        "  python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution contribute\n"
        "\n"
        "Contribute to the spec (on a machine you control):\n"
        "  make build                 # wrote spec to openrpc.json\n"
        "  npm run build:docs && npm run watch && npm run start\n"
        "  make test                  # speccheck against tests/\n"
        f"  Hive rpc-compat: {HIVE_RPC_COMPAT_URL}\n"
        f"  {CONTRIBUTING_URL}\n"
        "\n"
        "Engine API is a separate JWT-authenticated port (default 8551) for "
        f"the consensus layer. {ENGINE_AUTH_URL}\n"
        "\n"
        "This agent is read-only spec lookup. It does not connect to an "
        "Ethereum node, send eth_sendRawTransaction, sign, or call engine_* "
        "or testing_commitBlockV1.\n"
        "\n"
        "Not Bitcoin Core JSON-RPC. bitcoind methods stay on `rpc` / "
        f"`lookup_rpc`. OpenRPC: {OPENRPC_URL}"
    )


def _contribute_text() -> str:
    return (
        "Contributing to ethereum/execution-apis (from the quickstart):\n"
        "\n"
        f"Docs: {QUICKSTART_URL}\n"
        f"CONTRIBUTING.md: {CONTRIBUTING_URL}\n"
        f"Contributors guide: {CONTRIBUTORS_GUIDE_URL}\n"
        f"Tests: {TESTS_DOC_URL}\n"
        f"Pin used here: {COMMIT_URL}\n"
        "\n"
        "1. Compile OpenRPC YAML into one document:\n"
        "     make build\n"
        "   writes openrpc.json (all schema $refs resolved) plus "
        "refs-openrpc.json.\n"
        "2. Preview docs locally:\n"
        "     npm run build:docs\n"
        "     npm run watch     # rebuild spec + copy README → quickstart.md\n"
        "     npm run start     # Docusaurus at http://localhost:3000\n"
        "   Search index needs `npm run build:docs` then `npm run serve`.\n"
        "3. Validate:\n"
        "     make test         # speccheck against tests/\n"
        "     make lint         # openrpc-linter\n"
        "     pip install pyspelling && pyspelling -c spellcheck.yaml\n"
        "4. Hive rpc-compat clones this repo (default branch main) and runs "
        f"the tests/ fixtures against clients. Results: {HIVE_RESULTS_URL}\n"
        "5. GraphQL: `npm run graphql:schema` then "
        "`npm run graphql:validate`.\n"
        "\n"
        "Versioning is semver. Major = hive/rpc-compat breaking changes or "
        "incompatible method/shape changes. Minor = backwards-compatible "
        "features. Patch = docs/tooling/backwards-compatible fixes.\n"
        "\n"
        "Client consensus is required (ACDT, Eth R&D #json-rpc-api, RPC "
        "Standards). New methods typically land in go-ethereum so rpctestgen "
        "can emit .io fixtures.\n"
        "\n"
        "This agent only explains the workflow. It does not open PRs against "
        "execution-apis, run hive, or talk to a live execution client."
    )


def _graphql_text(query: str = "") -> str:
    payload = load_index().get("graphql") or {}
    queries = payload.get("query") or []
    mutations = payload.get("mutation") or []
    needle = (query or "").strip().lower()
    if needle in {"", "overview", "help", "list"}:
        lines = [
            "Ethereum execution GraphQL (EIP-1767): Besu and Geth expose this "
            "schema. The live schema in execution-apis is generated from a node "
            f"(`npm run graphql:schema`). {EIP_1767_URL}",
            f"Schema: {GRAPHQL_SCHEMA_URL}",
            "",
            "Query fields:",
        ]
        for field in queries:
            args = f"({field['args']})" if field.get("args") else "()"
            desc = field.get("description") or ""
            lines.append(f"- {field.get('name')}{args}" + (f" — {desc}" if desc else ""))
        lines.append("")
        lines.append("Mutation fields:")
        for field in mutations:
            args = f"({field['args']})" if field.get("args") else "()"
            desc = field.get("description") or ""
            lines.append(f"- {field.get('name')}{args}" + (f" — {desc}" if desc else ""))
        lines.extend(
            [
                "",
                "sendRawTransaction is a mutation. This agent will not submit "
                "transactions. Spec only.",
                f"JSON-RPC counterpart: {DOCS_URL}",
            ]
        )
        return "\n".join(lines)
    haystacks = list(queries) + list(mutations)
    hits = [
        field
        for field in haystacks
        if needle in str(field.get("name") or "").lower()
        or needle in str(field.get("description") or "").lower()
    ]
    if not hits:
        return (
            f"No GraphQL field matching {query!r}. Known queries: "
            + ", ".join(str(f.get("name")) for f in queries)
            + ". Mutations: "
            + ", ".join(str(f.get("name")) for f in mutations)
            + "."
        )
    lines = [f"GraphQL field(s) matching {query!r}:"]
    for field in hits:
        kind = "mutation" if field in mutations else "query"
        args = f"({field['args']})" if field.get("args") else "()"
        lines.append(f"- {kind} {field.get('name')}{args}")
        if field.get("description"):
            lines.append(f"  {field['description']}")
    lines.append("Spec only. This agent will not query a GraphQL endpoint.")
    return "\n".join(lines)


@tool
def execution_apis_overview() -> str:
    """Explain the Ethereum Execution APIs OpenRPC spec, GraphQL, and contributing.

    Read-only. Does not connect to an execution client or send transactions.
    """
    return _overview_text()


@tool
def execution_apis_contribute() -> str:
    """How to compile, test, and preview ethereum/execution-apis locally.

    Covers make build, Docusaurus docs, speccheck, hive rpc-compat, GraphQL.
    Read-only. Does not open PRs or talk to a node.
    """
    return _contribute_text()


@tool
def execution_apis_method(name: str) -> str:
    """Look up one Ethereum execution JSON-RPC method from the bundled OpenRPC spec.

    Pass eth_blockNumber, engine_newPayloadV3, or a unique suffix such as
    blockNumber. Spec only — never calls a node.
    """
    raw = (name or "").strip()
    if _secret_query(raw):
        return "Do not paste seed phrases, private keys, JWT secrets, or API keys."
    if not raw:
        return (
            "Provide an Execution API method such as eth_blockNumber, "
            "eth_call, or engine_exchangeCapabilities."
        )
    matches, how = resolve_methods(raw)
    if how == "empty" or not load_methods():
        return (
            "The Execution APIs index is missing. Run "
            "generate_execution_apis_index.py."
        )
    if not matches:
        namespaces = ", ".join(method_namespaces())
        return (
            f"No Execution API method matching {raw!r}. "
            f"Namespaces: {namespaces}. Try `execution list eth`."
        )
    if len(matches) == 1:
        return format_method(matches[0])
    lines = [f"Multiple Execution API methods match {raw!r}:"]
    for entry in matches[:20]:
        summary = (entry.get("summary") or "").splitlines()[0]
        lines.append(f"- {entry.get('name')} — {summary}")
    if len(matches) > 20:
        lines.append(f"... and {len(matches) - 20} more")
    lines.append("Pass a full method name to see params and the spec example.")
    return "\n".join(lines)


@tool
def execution_apis_list(namespace: str = "") -> str:
    """List bundled Ethereum execution JSON-RPC methods, optionally by namespace.

    Namespaces: eth, engine, debug, txpool, net, testing. Empty lists all.
    """
    raw = (namespace or "").strip()
    if _secret_query(raw):
        return "Do not paste seed phrases, private keys, JWT secrets, or API keys."
    methods = load_methods()
    if not methods:
        return (
            "The Execution APIs index is missing. Run "
            "generate_execution_apis_index.py."
        )
    wanted = raw.lower().replace("-", "_")
    if wanted in {"write", "sign", "send"}:
        wanted_kind = "write"
        wanted = ""
    elif wanted in {"engine"}:
        wanted_kind = "engine"
        wanted = "engine"
    elif wanted in {"read"}:
        wanted_kind = "read"
        wanted = ""
    elif wanted in {"testing", "test"}:
        wanted_kind = "testing"
        wanted = "testing"
    else:
        wanted_kind = ""
    token = _METHOD_TOKEN.search(raw)
    if token:
        return execution_apis_method(token.group(1))
    rows: list[dict[str, Any]] = []
    for entry in methods.values():
        ns = str(entry.get("namespace") or "")
        kind = str(entry.get("kind") or "read")
        if wanted and wanted not in {ns, str(entry.get("name") or "").lower()}:
            if wanted != kind:
                continue
        if wanted_kind and kind != wanted_kind:
            continue
        rows.append(entry)
    rows.sort(key=lambda item: str(item.get("name") or ""))
    if not rows:
        known = ", ".join(method_namespaces())
        return (
            f"No Execution API methods for {namespace!r}. "
            f"Known namespaces: {known}."
        )
    header = f"{len(rows)} Execution API method(s)"
    if wanted:
        header += f" in {wanted!r}"
    lines = [
        header + f" from ethereum/execution-apis@{SPEC_COMMIT[:7]}:",
    ]
    for entry in rows:
        summary = (entry.get("summary") or "").splitlines()[0]
        lines.append(f"- {entry.get('name')} ({entry.get('kind')}): {summary}")
    lines.append(
        "Spec only. This agent will not call an execution client. "
        f"Docs: {DOCS_URL}"
    )
    return "\n".join(lines)


@tool
def execution_apis_graphql(query: str = "") -> str:
    """List or look up Ethereum execution GraphQL fields from EIP-1767.

    Empty lists Query and Mutation fields. Pass a field name to filter.
    Spec only — never queries a node.
    """
    raw = (query or "").strip()
    if _secret_query(raw):
        return "Do not paste seed phrases, private keys, JWT secrets, or API keys."
    return _graphql_text(raw)


def execution_from_arg(text: str) -> str:
    """Map a local CLI argument onto an Execution APIs tool."""
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw or lower in {
        "overview",
        "help",
        "docs",
        "spec",
        "openrpc",
        "json-rpc",
        "jsonrpc",
    }:
        return execution_apis_overview()
    if re.search(r"^(contribute|contributing|quickstart|build|hive|docs-build)\b", lower):
        return execution_apis_contribute()
    if re.search(r"^(graphql|gql|schema)\b", lower):
        rest = re.sub(r"^(graphql|gql|schema)\b", "", raw, flags=re.I).strip()
        return execution_apis_graphql(rest)
    list_match = re.match(r"^(list|methods|ns|namespace)\b(?:\s+(.*))?$", raw, re.I)
    if list_match:
        return execution_apis_list(list_match.group(2) or "")
    method_match = re.match(
        r"^(method|lookup|rpc|call)\b(?:\s+(.*))?$",
        raw,
        re.I,
    )
    if method_match:
        rest = (method_match.group(2) or "").strip()
        if not rest:
            return execution_apis_list()
        return execution_apis_method(rest)
    if lower in method_namespaces() or lower in {
        "write",
        "read",
        "engine",
        "testing",
        "test",
        "sign",
        "send",
    }:
        return execution_apis_list(raw)
    if re.search(r"\b(contribute|quickstart|hive|speccheck|docusaurus)\b", lower):
        return execution_apis_contribute()
    if re.search(r"\b(graphql|eip-1767|eip1767)\b", lower):
        rest = re.sub(r"\b(graphql|eip-1767|eip1767|schema|field)\b", " ", raw, flags=re.I)
        return execution_apis_graphql(rest)
    if re.search(r"\b(list|methods|namespace)\b", lower):
        rest = re.sub(r"\b(list|methods|namespace|namespaces|of|for|the)\b", " ", raw, flags=re.I)
        return execution_apis_list(rest)
    return execution_apis_method(raw)
