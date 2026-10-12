from __future__ import annotations

import json
import unittest
from pathlib import Path

from bitcoin_tools import developer_howto
from execution_apis import (
    COMMIT_URL,
    DOCS_URL,
    GITHUB_URL,
    QUICKSTART_URL,
    SPEC_COMMIT,
    SPEC_VERSION,
    classify_method,
    execution_apis_contribute,
    execution_apis_graphql,
    execution_apis_list,
    execution_apis_method,
    execution_apis_overview,
    execution_from_arg,
    load_index,
    load_methods,
    resolve_methods,
    schema_label,
)
from local_cli import route_query

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERVIEW_DOC = REPO_ROOT / "BitcoinAgent" / "EXECUTION_APIS.md"
INDEX_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "execution_apis_index.json"
)


class ExecutionApisIndexTests(unittest.TestCase):
    def test_bundled_index_matches_pin(self) -> None:
        self.assertTrue(INDEX_PATH.is_file())
        payload = load_index()
        self.assertEqual(payload["commit"], SPEC_COMMIT)
        self.assertEqual(payload["version"], SPEC_VERSION)
        methods = load_methods()
        self.assertGreaterEqual(len(methods), 80)
        self.assertIn("eth_blockNumber", methods)
        self.assertIn("eth_sendRawTransaction", methods)
        self.assertIn("engine_newPayloadV3", methods)
        self.assertIn("net_version", methods)
        self.assertEqual(methods["eth_blockNumber"]["kind"], "read")
        self.assertEqual(methods["eth_sendRawTransaction"]["kind"], "write")
        self.assertEqual(methods["engine_newPayloadV3"]["kind"], "engine")
        self.assertEqual(methods["testing_commitBlockV1"]["kind"], "testing")
        graphql = payload["graphql"]
        self.assertIn("chainID", [f["name"] for f in graphql["query"]])
        self.assertEqual(graphql["mutation"][0]["name"], "sendRawTransaction")


class ExecutionApisOverviewTests(unittest.TestCase):
    def test_overview_covers_spec_and_refuses_node_calls(self) -> None:
        text = execution_apis_overview()
        lowered = text.lower()
        self.assertIn(GITHUB_URL, text)
        self.assertIn(DOCS_URL, text)
        self.assertIn(QUICKSTART_URL, text)
        self.assertIn(SPEC_COMMIT[:12], text)
        self.assertIn("make build", lowered)
        self.assertIn("does not connect", lowered)
        self.assertIn("eth_sendrawtransaction", lowered)
        self.assertIn("engine_*", lowered)

    def test_repo_overview_doc_exists(self) -> None:
        self.assertTrue(OVERVIEW_DOC.is_file())
        body = OVERVIEW_DOC.read_text(encoding="utf-8")
        self.assertIn(GITHUB_URL, body)
        self.assertIn(QUICKSTART_URL, body)
        self.assertIn(SPEC_COMMIT[:12], body)
        self.assertIn("does **not** connect to a node", body)
        self.assertIn("engine_*", body)

    def test_howto_execution_topic(self) -> None:
        text = developer_howto("execution")
        self.assertIn(SPEC_COMMIT[:8], text)
        self.assertIn(QUICKSTART_URL, text)
        self.assertEqual(developer_howto("execution-apis"), text)
        self.assertEqual(developer_howto("openrpc"), text)
        self.assertEqual(developer_howto("engine-api"), text)
        self.assertIn("does not connect to a node", text.lower())


class ExecutionApisMethodTests(unittest.TestCase):
    def test_lookup_eth_block_number(self) -> None:
        text = execution_apis_method("eth_blockNumber")
        self.assertIn("Execution API: eth_blockNumber", text)
        self.assertIn("Kind: read", text)
        self.assertIn("src/eth/client.yaml", text)
        self.assertIn("0x2377", text)
        self.assertIn("will not call an execution client", text.lower())

    def test_suffix_and_case(self) -> None:
        matches, how = resolve_methods("blockNumber")
        self.assertEqual(how, "suffix")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "eth_blockNumber")
        text = execution_apis_method("ETH_CHAINID")
        self.assertIn("Execution API: eth_chainId", text)

    def test_write_and_engine_banners(self) -> None:
        send = execution_apis_method("eth_sendRawTransaction")
        self.assertIn("Kind: write", send)
        self.assertIn("will not", send.lower())
        engine = execution_apis_method("engine_newPayloadV3")
        self.assertIn("Kind: engine", engine)
        self.assertIn("8551", engine)
        self.assertIn("will not send", engine.lower())

    def test_unknown_and_empty(self) -> None:
        self.assertIn("No Execution API method matching", execution_apis_method("not_a_method"))
        self.assertIn("Provide an Execution API method", execution_apis_method(""))

    def test_refuses_secrets(self) -> None:
        self.assertIn("seed", execution_apis_method("my seed phrase apple").lower())
        self.assertIn("jwt", execution_apis_method("here is the jwt secret").lower())
        engine_auth = execution_apis_method("engine_exchangeCapabilities")
        self.assertIn("Execution API: engine_exchangeCapabilities", engine_auth)

    def test_multiple_matches(self) -> None:
        text = execution_apis_method("getPayload")
        self.assertIn("Multiple Execution API methods", text)
        self.assertIn("engine_getPayloadV1", text)


class ExecutionApisListTests(unittest.TestCase):
    def test_list_eth_namespace(self) -> None:
        text = execution_apis_list("eth")
        self.assertIn("eth_blockNumber", text)
        self.assertIn("eth_call", text)
        self.assertNotIn("engine_newPayloadV1", text)
        self.assertIn("Spec only", text)

    def test_list_write_kind(self) -> None:
        text = execution_apis_list("write")
        self.assertIn("eth_sendRawTransaction", text)
        self.assertIn("eth_sign", text)
        self.assertNotIn("eth_blockNumber (", text)

    def test_list_unknown(self) -> None:
        text = execution_apis_list("spaceships")
        self.assertIn("No Execution API methods", text)
        self.assertIn("eth", text)


class ExecutionApisGraphqlAndContributeTests(unittest.TestCase):
    def test_graphql_lists_query_and_mutation(self) -> None:
        text = execution_apis_graphql()
        self.assertIn("chainID", text)
        self.assertIn("sendRawTransaction", text)
        self.assertIn("EIP-1767", text)
        self.assertIn("will not submit", text.lower())

    def test_graphql_filter(self) -> None:
        text = execution_apis_graphql("block")
        self.assertIn("query block", text)

    def test_contribute_quickstart(self) -> None:
        text = execution_apis_contribute()
        self.assertIn(QUICKSTART_URL, text)
        self.assertIn("make build", text)
        self.assertIn("npm run build:docs", text)
        self.assertIn("speccheck", text)
        self.assertIn("hive", text.lower())
        self.assertIn("does not open prs", text.lower())


class GeneratorHelperTests(unittest.TestCase):
    def test_classify_method(self) -> None:
        self.assertEqual(classify_method("eth_blockNumber"), "read")
        self.assertEqual(classify_method("eth_sendRawTransaction"), "write")
        self.assertEqual(classify_method("engine_forkchoiceUpdatedV3"), "engine")
        self.assertEqual(classify_method("testing_buildBlockV1"), "testing")

    def test_schema_label(self) -> None:
        self.assertEqual(schema_label({"$ref": "#/components/schemas/uint"}), "uint")
        self.assertEqual(
            schema_label({"oneOf": [{"$ref": "#/a/notFound"}, {"$ref": "#/a/Block"}]}),
            "notFound | Block",
        )
        self.assertEqual(schema_label({"type": "array", "items": {"type": "string"}}), "array[string]")


class ExecutionApisLocalCliTests(unittest.TestCase):
    def test_routes_overview_method_list(self) -> None:
        overview = route_query("execution")
        self.assertIn(COMMIT_URL, overview)
        method = route_query("execution eth_blockNumber")
        self.assertIn("Execution API: eth_blockNumber", method)
        listed = route_query("execution list eth")
        self.assertIn("eth_getBalance", listed)
        contribute = route_query("execution contribute")
        self.assertIn(QUICKSTART_URL, contribute)
        graphql = route_query("execution graphql")
        self.assertIn("chainID", graphql)

    def test_bare_method_name(self) -> None:
        text = route_query("eth_blockNumber")
        self.assertIn("Execution API: eth_blockNumber", text)

    def test_natural_language(self) -> None:
        text = route_query("what does eth_call do in the execution apis")
        self.assertIn("Execution API: eth_call", text)
        overview = route_query("ethereum execution apis quickstart")
        self.assertIn(QUICKSTART_URL, overview)

    def test_help_lists_execution(self) -> None:
        text = route_query("help")
        self.assertIn("execution", text)
        self.assertIn("graphql", text)

    def test_howto_route(self) -> None:
        text = route_query("howto execution")
        self.assertIn(SPEC_COMMIT[:8], text)
        self.assertIn("make build", text)

    def test_from_arg_helpers(self) -> None:
        self.assertIn("eth_blockNumber", execution_from_arg("list eth"))
        self.assertIn("Execution API: eth_chainId", execution_from_arg("eth_chainId"))
        self.assertIn("make build", execution_from_arg("quickstart"))

    def test_bitcoin_rpc_still_works(self) -> None:
        text = route_query("rpc getblockcount")
        self.assertIn("RPC: getblockcount", text)
        self.assertNotIn("Execution API:", text)


class ExecutionApisIndexIntegrityTests(unittest.TestCase):
    def test_index_json_is_object_map(self) -> None:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        for name, entry in payload["methods"].items():
            self.assertEqual(entry["name"], name)
            self.assertIn(entry["kind"], {"read", "write", "engine", "testing"})
            self.assertTrue(entry["source"].startswith("src/"))
            self.assertIn("params", entry)
            self.assertIn("summary", entry)


if __name__ == "__main__":
    unittest.main()
