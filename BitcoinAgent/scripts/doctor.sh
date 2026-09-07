#!/usr/bin/env bash
# Report what is already usable and what is still missing.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/app/BitcoinAgent"
ok=0
warn=0
fail=0

say() { printf '%s\n' "$*"; }
pass() { say "  [ok]  $*"; ok=$((ok + 1)); }
note() { say "  [--]  $*"; warn=$((warn + 1)); }
need() { say "  [!!]  $*"; fail=$((fail + 1)); }

have() { command -v "$1" >/dev/null 2>&1; }

say "BitcoinAgent doctor"
say "==================="
say

say "Works right now (no AWS)"
if have python3; then
  ver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
    && pass "python3 $ver" \
    || need "python3 $ver (need 3.10+)"
else
  need "python3 not on PATH"
fi

if [[ -f "$APP/data/rpc_index.json" ]]; then
  count="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$APP/data/rpc_index.json" 2>/dev/null || echo 0)"
  pass "bundled RPC index ($count methods)"
else
  need "missing $APP/data/rpc_index.json — run generate_rpc_index.py"
fi

if [[ -f "$APP/local_cli.py" ]]; then
  pass "local CLI: python3 $APP/local_cli.py \"What does getblockcount do?\""
else
  need "local_cli.py is missing"
fi

if have python3 && [[ -f "$APP/tests/test_bitcoin_tools.py" ]]; then
  if (cd "$APP" && python3 -m unittest discover -s tests -q); then
    pass "unit tests passed"
  else
    need "unit tests failed (cd $APP && python3 -m unittest discover -s tests)"
  fi
fi

say
say "Needed only for the live model (agentcore dev / deploy)"
if have node; then
  node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  if [[ "$node_major" -ge 20 ]]; then
    pass "node $(node -v)"
  else
    need "node $(node -v) (need 20+)"
  fi
else
  note "node not installed (needed for the AgentCore CLI)"
fi

if have npm; then
  pass "npm $(npm -v)"
else
  note "npm not installed"
fi

if have uv; then
  pass "uv $(uv --version 2>/dev/null | awk '{print $2}')"
else
  note "uv not installed — https://docs.astral.sh/uv/"
fi

if have agentcore; then
  pass "agentcore $(agentcore --version 2>/dev/null | head -n1)"
else
  note "agentcore CLI missing — npm install -g @aws/agentcore"
fi

if have aws; then
  if aws sts get-caller-identity >/dev/null 2>&1; then
    pass "AWS credentials resolve ($(aws sts get-caller-identity --query Account --output text 2>/dev/null))"
  else
    note "aws CLI present but credentials do not work yet (aws configure)"
  fi
else
  note "aws CLI not installed — needed to deploy and to call the runtime"
fi

if [[ -f "$ROOT/.local/deploy.env" ]]; then
  pass "deploy env exists at $ROOT/.local/deploy.env"
else
  note "not deployed yet — after agentcore deploy run $ROOT/scripts/after_deploy.sh"
fi

say
say "Summary: $ok ok, $warn optional/missing for AWS, $fail blocking"
say "Next: python3 $APP/local_cli.py"
if [[ "$fail" -gt 0 ]]; then
  exit 1
fi
exit 0
