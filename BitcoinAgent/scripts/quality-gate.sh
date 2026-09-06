#!/bin/bash
# quality-gate.sh — run after deploy + at least one invoke in CI/CD
set -euo pipefail

RUNTIME="${RUNTIME:-BitcoinAgent}"
EVALUATOR="${EVALUATOR:-Builtin.Helpfulness}"
THRESHOLD="${THRESHOLD:-0.7}"

echo "Running quality gate eval..."
result=$(agentcore run eval \
  --runtime "$RUNTIME" \
  --evaluator "$EVALUATOR" \
  --days 1 \
  --json)

score=$(echo "$result" | jq -r '.run.results[0].aggregateScore // empty')

if [ -z "$score" ]; then
  echo "No eval data found. Invoke the agent, wait ~15 seconds, then re-run."
  exit 1
fi

echo "Quality score: $score (threshold: $THRESHOLD)"

if awk -v s="$score" -v t="$THRESHOLD" 'BEGIN{exit !(s<t)}'; then
  echo "Quality gate FAILED: score $score < $THRESHOLD"
  exit 1
fi

echo "Quality gate PASSED"
