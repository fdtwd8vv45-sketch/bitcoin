# Phantom Connect SDK

Phantom Connect is Phantom's open-source multi-platform SDK suite for
onboarding users with embedded wallets (Google / Apple) or the Phantom
browser extension. BitcoinAgent reads the **docs** and does **read-only**
npm version / CLI checks. It does **not** connect a wallet, login, sign,
send, or swap.

Official docs:

- Source: https://github.com/phantom/phantom-connect-sdk
- SDK comparison: https://docs.phantom.com/wallet-sdks-overview
- Connect modal / spending limits: https://docs.phantom.com/phantom-connect
- Docs MCP: https://docs.phantom.com/mcp
- Docs MCP setup: https://docs.phantom.com/resources/mcp-server
- Portal (App ID): https://phantom.com/portal
- CLI: https://docs.phantom.com/phantom-cli
- Wallet MCP (not attached here): https://docs.phantom.com/phantom-mcp-server

## What this agent will do

| Action | How |
| --- | --- |
| Read Phantom docs | Cursor `phantom-docs` MCP, or `PHANTOM_DOCS_MCP=1` on the runtime |
| Explain SDKs / Portal | `phantom_connect_overview` |
| npm latest versions | `phantom_connect_packages` → `GET https://registry.npmjs.org/@phantom%2f…/latest` |
| CLI present? | `phantom --version` only |

Client packages: `@phantom/react-sdk`, `@phantom/browser-sdk`,
`@phantom/react-native-sdk`. Adjacent CLI: `@phantom/cli`.

## What this agent will not do

Connect a wallet, `phantom login`, sign, send, swap, perps, or run
`phantom --mcp`. The Phantom **wallet** MCP (`@phantom/mcp-server`) stays
off because those tools can move funds. Install it on a machine you
control if you need an agent wallet:

```bash
npx -y @phantom/mcp-server@latest
```

On a machine you control:

```bash
npm install @phantom/react-sdk          # or browser-sdk / react-native-sdk
npm install -g @phantom/cli
phantom login                           # opens a browser; not wrapped here
```

Get an App ID from [Phantom Portal](https://phantom.com/portal) → app →
Set Up. Allowlist domains and redirect URLs. `PHANTOM_APP_ID` is safe to
put in client code; this agent still never prints it.

## Cursor (local agents)

`.cursor/mcp.json` already includes the read-only docs server:

| Server | URL | Auth |
| --- | --- | --- |
| `phantom-docs` | `https://docs.phantom.com/mcp` | none |

BitcoinAgent attaches the same server when `PHANTOM_DOCS_MCP=1`. Wallet
MCP (`npx -y @phantom/mcp-server@latest`) is not attached.

## Check from this tree (no AWS)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom packages
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom packages react
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py phantom status
```

## Critical SDK rules (for apps you build elsewhere)

1. Use `signAndSendTransaction` — `signTransaction` is not supported for
   embedded wallets.
2. Wrap async SDK calls in try/catch — users can reject prompts.
3. Check `isConnected` before signing.
4. React Native: `react-native-get-random-values` must be the first import.
5. BrowserSDK must be a singleton.
6. Embedded wallet spending limit: $1,000 USD per app per user per day.
7. Social login sessions last 7 days from the last auth event.

## Not the same as Bitcoin Core

Phantom Bitcoin addresses are not bitcoind wallets. Coins sent to
`bitcoin-cli getnewaddress` will not appear in Phantom, and the reverse
is also true. The injected `window.phantom.bitcoin` provider is
deprecated; use Wallet Standard or the Connect SDKs. This agent still
will not sign or broadcast Bitcoin (or any other) transactions.
