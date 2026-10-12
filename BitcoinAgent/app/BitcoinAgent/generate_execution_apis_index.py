#!/usr/bin/env python3
"""Build the bundled Ethereum Execution APIs method index.

Downloads OpenRPC method YAML + GraphQL introspection from the pinned
ethereum/execution-apis commit and writes a compact JSON index. Runtime
tools load that file with the standard library only.

    python3 generate_execution_apis_index.py
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from execution_apis import SPEC_COMMIT, SPEC_VERSION, classify_method, schema_label

# Pin and version live in execution_apis.py (ethereum/execution-apis@34151926).
GITHUB_RAW = "https://raw.githubusercontent.com/ethereum/execution-apis"
METHOD_FILES = (
    "src/debug/getters.yaml",
    "src/debug/trace.yaml",
    "src/engine/openrpc/methods/blob.yaml",
    "src/engine/openrpc/methods/capabilities.yaml",
    "src/engine/openrpc/methods/forkchoice.yaml",
    "src/engine/openrpc/methods/inclusion_list.yaml",
    "src/engine/openrpc/methods/payload.yaml",
    "src/engine/openrpc/methods/transition_configuration.yaml",
    "src/eth/block.yaml",
    "src/eth/capabilities.yaml",
    "src/eth/client.yaml",
    "src/eth/execute.yaml",
    "src/eth/fee_market.yaml",
    "src/eth/fill.yaml",
    "src/eth/filter.yaml",
    "src/eth/sign.yaml",
    "src/eth/state.yaml",
    "src/eth/submit.yaml",
    "src/eth/subscribe.yaml",
    "src/eth/transaction.yaml",
    "src/testing/testing_buildBlockV1.yaml",
    "src/testing/testing_commitBlockV1.yaml",
    "src/txpool/pool.yaml",
)
GRAPHQL_FILE = "graphql.json"
_THIS_DIR = Path(__file__).resolve().parent
_INDEX_PATH = _THIS_DIR / "data" / "execution_apis_index.json"
_TIMEOUT_SECONDS = 30
_MAX_BYTES = 2_000_000
_MAX_EXAMPLE_CHARS = 360
_MAX_DESCRIPTION_CHARS = 1200
_USER_AGENT = "BitcoinAgent/1.0"


def _compact_json(value: Any) -> str:
    text = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    if len(text) <= _MAX_EXAMPLE_CHARS:
        return text
    return text[:_MAX_EXAMPLE_CHARS] + "…"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _fetch(path: str) -> bytes:
    url = f"{GITHUB_RAW}/{SPEC_COMMIT}/{path}"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/octet-stream", "User-Agent": _USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        raw = response.read(_MAX_BYTES + 1)
        status = getattr(response, "status", 200)
    if status != 200:
        raise SystemExit(f"HTTP {status} fetching {url}")
    if len(raw) > _MAX_BYTES:
        raise SystemExit(f"Response too large for {url}")
    return raw


def _compact_example(example: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(example, dict):
        return None
    params: list[dict[str, str]] = []
    raw_params = example.get("params") or []
    if isinstance(raw_params, list):
        for item in raw_params:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            if "value" not in item:
                params.append({"name": name, "value": ""})
                continue
            params.append({"name": name, "value": _compact_json(item.get("value"))})
    result_value = ""
    result = example.get("result")
    if isinstance(result, dict) and "value" in result:
        result_value = _compact_json(result.get("value"))
    return {
        "name": str(example.get("name") or ""),
        "params": params,
        "result": result_value,
    }


def compact_method(raw: dict[str, Any], source: str) -> dict[str, Any]:
    name = str(raw.get("name") or "").strip()
    if not name:
        raise ValueError(f"Method in {source} is missing a name")
    params: list[dict[str, Any]] = []
    for item in raw.get("params") or []:
        if not isinstance(item, dict):
            continue
        schema = item.get("schema") if isinstance(item.get("schema"), dict) else {}
        enum_values = schema.get("enum") if isinstance(schema, dict) else None
        params.append(
            {
                "name": str(item.get("name") or ""),
                "required": bool(item.get("required", False)),
                "schema": schema_label(schema),
                "enum": [str(v) for v in enum_values] if isinstance(enum_values, list) else [],
            }
        )
    result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
    errors: list[str] = []
    for err in raw.get("errors") or []:
        if isinstance(err, dict):
            code = err.get("code")
            message = err.get("message") or ""
            errors.append(f"{code}: {message}".strip(": "))
    error_groups: list[str] = []
    for group in raw.get("error-groups") or []:
        if isinstance(group, dict) and isinstance(group.get("$ref"), str):
            error_groups.append(group["$ref"].rsplit("/", 1)[-1])
    docs = raw.get("externalDocs") if isinstance(raw.get("externalDocs"), dict) else {}
    examples: list[dict[str, Any]] = []
    for example in (raw.get("examples") or [])[:2]:
        compact = _compact_example(example) if isinstance(example, dict) else None
        if compact:
            examples.append(compact)
    description = str(raw.get("description") or "").strip()
    return {
        "name": name,
        "namespace": name.split("_", 1)[0],
        "kind": classify_method(name),
        "summary": str(raw.get("summary") or "").strip(),
        "description": _truncate(description, _MAX_DESCRIPTION_CHARS),
        "params": params,
        "result_name": str(result.get("name") or ""),
        "result_schema": schema_label(result.get("schema")),
        "errors": errors,
        "error_groups": error_groups,
        "external_docs_url": str(docs.get("url") or ""),
        "external_docs": str(docs.get("description") or ""),
        "examples": examples,
        "source": source,
    }


def compact_graphql(introspection: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    schema = introspection.get("__schema") if isinstance(introspection, dict) else {}
    types = {
        item["name"]: item
        for item in (schema.get("types") or [])
        if isinstance(item, dict) and item.get("name")
    }
    out: dict[str, list[dict[str, str]]] = {"query": [], "mutation": []}
    for key, type_name in (("query", "Query"), ("mutation", "Mutation")):
        type_obj = types.get(type_name) or {}
        for field in type_obj.get("fields") or []:
            if not isinstance(field, dict) or not field.get("name"):
                continue
            args = [str(arg.get("name") or "") for arg in (field.get("args") or []) if isinstance(arg, dict)]
            desc = str(field.get("description") or "").strip()
            out[key].append(
                {
                    "name": str(field["name"]),
                    "args": ", ".join(a for a in args if a),
                    "description": _truncate(desc.splitlines()[0] if desc else "", 240),
                }
            )
    return out


def build_index() -> dict[str, Any]:
    methods: dict[str, dict[str, Any]] = {}
    for relpath in METHOD_FILES:
        payload = yaml.safe_load(_fetch(relpath).decode("utf-8"))
        if not isinstance(payload, list):
            raise SystemExit(f"{relpath} did not parse as a YAML list")
        for item in payload:
            if not isinstance(item, dict):
                continue
            entry = compact_method(item, relpath)
            methods[entry["name"]] = entry
    graphql_raw = json.loads(_fetch(GRAPHQL_FILE).decode("utf-8"))
    return {
        "commit": SPEC_COMMIT,
        "version": SPEC_VERSION,
        "source": "https://github.com/ethereum/execution-apis",
        "docs": "https://ethereum.github.io/execution-apis/",
        "quickstart": "https://ethereum.github.io/execution-apis/docs/quickstart/",
        "methods": methods,
        "graphql": compact_graphql(graphql_raw),
    }


def write_index(dest: Path | None = None) -> Path:
    dest = dest or _INDEX_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    index = build_index()
    dest.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return dest


def main() -> None:
    dest = write_index()
    payload = json.loads(dest.read_text(encoding="utf-8"))
    print(
        f"Wrote {dest} ({len(payload['methods'])} methods, "
        f"commit {payload['commit'][:12]})"
    )


if __name__ == "__main__":
    main()
