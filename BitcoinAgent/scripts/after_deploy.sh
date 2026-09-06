#!/usr/bin/env bash
# After `agentcore deploy`, collect ARNs, write a reusable session, and print
# the remaining Cedar / invoke steps. Does not change policy mode.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL="$ROOT/.local"
mkdir -p "$LOCAL"

if ! command -v agentcore >/dev/null 2>&1; then
  echo "agentcore CLI not found. Install with: npm install -g @aws/agentcore" >&2
  exit 1
fi

echo "Fetching access info..."
agentcore fetch access --name BitcoinAgent --type agent > "$LOCAL/agent-access.txt" 2>&1 || true
agentcore fetch access --name BitcoinGateway > "$LOCAL/gateway-access.txt" 2>&1 || true
agentcore status > "$LOCAL/status.txt" 2>&1 || true

extract_arn() {
  local file="$1" needle="$2"
  grep -Eo "arn:aws[a-zA-Z-]*:bedrock-agentcore:[^[:space:]\"']+" "$file" 2>/dev/null \
    | grep -i "$needle" \
    | head -n1 || true
}

RUNTIME_ARN="$(extract_arn "$LOCAL/agent-access.txt" runtime)"
if [[ -z "$RUNTIME_ARN" ]]; then
  RUNTIME_ARN="$(extract_arn "$LOCAL/status.txt" runtime)"
fi
GATEWAY_ARN="$(extract_arn "$LOCAL/gateway-access.txt" gateway)"
if [[ -z "$GATEWAY_ARN" ]]; then
  GATEWAY_ARN="$(extract_arn "$LOCAL/status.txt" gateway)"
fi

SESSION_ID="$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"
USER_ID="${BITCOIN_AGENT_USER:-default-user}"

{
  echo "AGENT_RUNTIME_ARN=${RUNTIME_ARN}"
  echo "AGENTCORE_GATEWAY_ARN=${GATEWAY_ARN}"
  echo "BITCOIN_AGENT_SESSION=${SESSION_ID}"
  echo "BITCOIN_AGENT_USER=${USER_ID}"
} > "$LOCAL/deploy.env"

if [[ -n "$GATEWAY_ARN" ]]; then
  sed "s|GATEWAY_ARN|${GATEWAY_ARN}|g" "$ROOT/policies/allow_read_tools.cedar.template" \
    > "$LOCAL/allow_read_tools.cedar"
fi

echo
echo "Wrote $LOCAL/deploy.env"
if [[ -n "$RUNTIME_ARN" ]]; then
  echo "  runtime  $RUNTIME_ARN"
else
  echo "  runtime ARN not found — inspect $LOCAL/agent-access.txt and $LOCAL/status.txt"
fi
if [[ -n "$GATEWAY_ARN" ]]; then
  echo "  gateway  $GATEWAY_ARN"
  echo "  cedar    $LOCAL/allow_read_tools.cedar"
else
  echo "  gateway ARN not found yet — re-run after the gateway finishes creating"
fi
echo "  session  $SESSION_ID  (reuse this for memory)"
echo
echo "Talk to the deployed agent (same session, so memory can attach):"
echo "  set -a && source $LOCAL/deploy.env && set +a"
echo "  python3 $ROOT/clients/python/invoke_agent.py \"My name is Alex and I work on Bitcoin Core RPC tests\""
echo
if [[ -n "$GATEWAY_ARN" ]]; then
  echo "Attach Cedar after you have reviewed the filled policy:"
  echo "  agentcore add policy --name allow_read_tools --engine BitcoinPolicy --source $LOCAL/allow_read_tools.cedar"
  echo "  agentcore logs --runtime BitcoinAgent --since 1h --query policy"
  echo "Leave BitcoinPolicy in LOG_ONLY until those logs look right."
fi
echo
echo "CloudWatch log retention (replace AGENT_ID from agentcore status):"
echo "  aws logs put-retention-policy --log-group-name /aws/bedrock-agentcore/runtimes/<AGENT_ID>-DEFAULT --retention-in-days 30"
