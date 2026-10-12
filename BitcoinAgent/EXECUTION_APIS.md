# Ethereum Execution APIs

The [Execution API specification](https://github.com/ethereum/execution-apis)
is the canonical JSON-RPC (OpenRPC) plus GraphQL interface that every
Ethereum execution client implements. BitcoinAgent looks up that **spec**.
It does **not** connect to a node, sign, send, or call the Engine API.

Official docs:

- Spec playground / methods: https://ethereum.github.io/execution-apis/
- Quickstart (compile, docs, hive): https://ethereum.github.io/execution-apis/docs/quickstart/
- Source: https://github.com/ethereum/execution-apis
- OpenRPC: https://open-rpc.org
- GraphQL (EIP-1767): https://eips.ethereum.org/EIPS/eip-1767
- Hive rpc-compat: https://github.com/ethereum/hive/tree/master/simulators/ethereum/rpc-compat

## Pin

The bundled method index is generated from OpenRPC YAML at:

- Tree: https://github.com/ethereum/execution-apis/tree/34151926fbf395e66797add1f60fd759681678e6
- Commit: https://github.com/ethereum/execution-apis/commit/34151926fbf395e66797add1f60fd759681678e6
  (`34151926` — *spec: allow EIP-1898 block objects in BlockNumberOrTagOrHash*)
- Published docs version on that site: `1.0.0-beta.7`

Refresh the index after bumping the pin:

```bash
cd BitcoinAgent/app/BitcoinAgent
python3 generate_execution_apis_index.py
```

## What this agent will do

| Action | How |
| --- | --- |
| Explain JSON-RPC + GraphQL + contributing | `execution_apis_overview` |
| Compile / docs / hive workflow | `execution_apis_contribute` (the quickstart) |
| Look up a method | `execution_apis_method` — params, result, spec example |
| List by namespace | `execution_apis_list` — `eth`, `engine`, `debug`, `txpool`, `net`, `testing` |
| GraphQL fields | `execution_apis_graphql` — EIP-1767 Query / Mutation |

Namespaces in the pin: `eth`, `net`, `engine`, `debug`, `txpool`, `testing`.

## What this agent will not do

It never opens an Ethereum JSON-RPC or GraphQL port. It will not call
`eth_sendTransaction`, `eth_sendRawTransaction`, `eth_sign`,
`eth_signTransaction`, `engine_*` (JWT on port 8551), or
`testing_commitBlockV1`. Engine authentication is documented at
`src/engine/authentication.md`; this agent does not mint or store a JWT.

On a machine you control:

```bash
git clone https://github.com/ethereum/execution-apis.git
cd execution-apis
make build          # writes openrpc.json
make test           # speccheck
npm run build:docs && npm run start
```

## Check from this tree (no AWS)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution eth_blockNumber
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution list eth
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution graphql
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py execution contribute
```

## Not the same as Bitcoin Core

`eth_blockNumber` is not `getblockcount`. Execution-apis methods are
Ethereum JSON-RPC. Bitcoin Core methods stay on `rpc` / `lookup_rpc`.
Verified contract *source* is a different tool (`source` /
`lookup_contract_source` via Etherscan).
