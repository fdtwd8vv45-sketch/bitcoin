# Etherscan statistics

The [charts and stats](https://etherscan.io/charts) pages on etherscan.io
are built from the Etherscan API v2 `stats` module (plus the gas
oracle). BitcoinAgent reads the **free** endpoints. It does **not**
call PRO daily-chart actions, send transactions, or attach the official
CLI.

Official docs:

- Charts: https://etherscan.io/charts
- Stats charts: https://etherscan.io/statscharts
- Endpoint showcase: https://docs.etherscan.io/endpoint-showcase/charts-and-stats
- `ethsupply2`: https://docs.etherscan.io/api-reference/endpoint/ethsupply2
- `ethprice`: https://docs.etherscan.io/api-reference/endpoint/ethprice
- `nodecount`: https://docs.etherscan.io/api-reference/endpoint/nodecount
- `gasoracle`: https://docs.etherscan.io/api-reference/endpoint/gasoracle
- Build with AI (MCP, CLI, skills): https://docs.etherscan.io/build-with-ai/introduction
- API dashboard: https://etherscan.io/apidashboard

## What this agent will do

| Action | How |
| --- | --- |
| Explain charts / stats / MCP / CLI | `etherscan_stats_overview` |
| Free snapshot (supply + price + nodes + gas) | `etherscan_stats` |
| ETH supply breakdown | `etherscan_eth_supply` → `module=stats&action=ethsupply2` |
| Native-token price | `etherscan_eth_price` → `module=stats&action=ethprice` |
| Discoverable nodes | `etherscan_node_count` → `module=stats&action=nodecount` |
| Gas oracle | `etherscan_gas_oracle` → `module=gastracker&action=gasoracle` |
| Key present? | `etherscan_stats_status` (never prints the key) |

Calls are allowlisted HTTPS GET to `api.etherscan.io` `/v2/api` only.
They need `ETHERSCAN_API_KEY` (query `apikey=`, never logged). One key
covers 60+ EVM chains; pass `chainid` or a name such as `ethereum`,
`arbitrum`, or `base` (default: Ethereum `1`).

Verified contract source is a different tool (`source` /
`lookup_contract_source`). Official data + docs MCP stay in
`.cursor/mcp.json`.

## What this agent will not do

PRO daily chart endpoints stay off: `dailytx`, `dailynewaddress`,
`dailygasused`, `ethdailyprice`, `dailyblkcount`, `nodecounthistory`,
`dailytxnfee`, `dailynetutilization`, and the rest of the paid stats
module. Use a paid plan or the official CLI on a machine you control.

This agent does not install `@etherscan/cli`, does not broadcast
(`eth_sendRawTransaction`), and does not treat CoinStats or mempool.space
Bitcoin fees as Etherscan numbers.

On a machine you control:

```bash
npm install -g @etherscan/cli
etherscan login
etherscan stats ethsupply2
etherscan stats ethprice
etherscan stats nodecount
etherscan gastracker oracle
```

## Check from this tree (no AWS)

```bash
export ETHERSCAN_API_KEY=your_key
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats snapshot
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats supply
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats price base
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats nodes
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats gas
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py etherscan-stats status
```

## Not the same as Bitcoin Core

`etherscan-stats supply` is ETH supply from Etherscan, not
`gettxoutsetinfo`. Bitcoin fees / tip / difficulty stay on `fees`,
`tip`, and `difficulty`. Execution-apis method names stay on
`execution`.
