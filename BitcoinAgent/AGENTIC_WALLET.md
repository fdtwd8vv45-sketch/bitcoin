# Agentic Wallet

OKX Agentic Wallet is a dedicated onchain wallet for AI agents. Key
generation, storage, and signing stay inside a TEE (Trusted Execution Environment).
This agent never sees the private key — and neither does the BitcoinAgent process.

BitcoinAgent remains a Bitcoin Core assistant. It explains Agentic Wallet
and can check whether the official `onchainos` CLI is installed or logged
in. It does **not** send, swap, trade, or sign.

Official docs:

- Overview: https://web3.okx.com/onchainos/dev-docs/wallet/agentic-wallet
- Install: https://web3.okx.com/onchainos/dev-docs/wallet/install-your-agentic-wallet
- x402 buyer payments: https://web3.okx.com/onchainos/dev-docs/payments/payment-use-buyer
- Skills / CLI: https://github.com/okx/onchainos-skills

## Why an agent wallet

- **Closed-loop execution** — From a signal to onchain settlement without
  copying keys into chat or a local `wallet.dat`.
- **Always on** — The wallet session can stay available while the operator
  is away. This agent still will not place trades for you.
- **Risk checks** — The official CLI can flag malicious approvals and
  unusual transfers before they are signed in the TEE.
- **Many accounts** — Up to 50 sub-wallets for isolated positions.
- **Autonomous payments** — Built on the x402 protocol so an agent can pay
  for data or APIs when a server returns HTTP 402.

## What it can do (in the official OKX CLI / skills)

- Multi-chain balances and receive addresses (EVM, Solana, Bitcoin, Sui)
- Risk detection and approval review
- Batch transfers and parallel accounts
- x402 / MPP payments when calling paid APIs
- Market data and onchain monitoring (separate OKX skills)
- Sign-in with email, Google, or Apple — no seed phrase to type here

BitcoinAgent does not wrap those write paths. Install the official
Onchain OS skills if you want the full wallet skill in Cursor.

## Install (single command)

Needs Node.js 18+. From a machine you control:

```bash
npx -y @okxweb3/onchainos-installer install
```

That installs the `onchainos` CLI (usually `~/.local/bin`) and the OKX
skills. Then sign in by asking an agent that has those skills:

```text
Log in to Agentic Wallet with email
```

or Google / Apple. The CLI returns a login URL. Open it in a browser,
complete OTP or OAuth, and the first wallet is created automatically.
The same email restores the same wallet.

Do not paste seed phrases, private keys, or OTP codes into BitcoinAgent
notes.

## Check from this tree (no AWS)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py agentic
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py agentic status
```

`agentic` prints this overview. `agentic status` looks for `onchainos`
on `PATH` and, if present, runs the read-only `onchainos wallet status`
command.

## Not the same as a Bitcoin Core wallet

| | Bitcoin Core | Agentic Wallet |
| --- | --- | --- |
| Keys | Local wallet / descriptors | TEE; not exportable to this agent |
| Network | Bitcoin | Multi-chain (EVM, Solana, Bitcoin, …) |
| This agent | Public lookup + RPC help | Overview + CLI status only |
| Move coins | `bitcoin-cli` on your node | Official `onchainos` CLI, not here |

A payment sent to a Core `getnewaddress` result will not appear in an
OKX Agentic Wallet, and the reverse is also true.
