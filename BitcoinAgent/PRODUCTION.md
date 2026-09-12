# Production readiness — BitcoinAgent

Inbound auth is **AWS_IAM** (not `NONE`). The gateway uses AWS_IAM as well.
Policy engine `BitcoinPolicy` starts in **LOG_ONLY**. Switch to ENFORCE only
after you deploy, attach the filled Cedar file, and review decision logs.

After the first deploy, run:

```bash
cd BitcoinAgent
./scripts/after_deploy.sh
```

That writes `.local/deploy.env` (runtime ARN, gateway ARN, session UUID) and
`.local/allow_read_tools.cedar`. Source the env file before invoking so you
do not have to mint session IDs by hand.

## Checklist

### IAM
- [ ] Execution role Bedrock access scoped to Claude Sonnet 4.5 (see `app/BitcoinAgent/iam/runtime-bedrock.json`, already referenced from `agentcore.json`)
- [ ] After deploy, confirm the role trust policy is limited to your account
- [ ] Callers have `bedrock-agentcore:InvokeAgentRuntime` only — do not grant `InvokeAgentRuntimeCommand` unless you need shell access

### Authentication
- [x] Runtime authorizer is `AWS_IAM`
- [x] Gateway authorizer is `AWS_IAM`
- [ ] If you later switch to JWT for a web app: set `CUSTOM_JWT` with discovery URL and `allowedAudience` or `allowedClients` to match the token claims

### Secrets
- [x] No API keys in agent code
- [x] Public mempool.space calls are allowlisted HTTPS GET only
- [x] Local notes refuse seed phrases / private keys / wallet passwords
- [x] Etherscan MCP uses `ETHERSCAN_API_KEY` in process env / Cursor `${env:…}` only (Gateway MCP targets cannot attach an API key)
- [ ] Register any future private API keys with `agentcore add credential` (never runtime env vars)

### Code quality
- [x] Input validation on prompt, userId, and sessionId
- [x] Errors return a generic message; details stay in logs
- [x] Memory and gateway are no-ops when their env vars are unset (`agentcore dev`)
- [x] `scripts/doctor.sh` and `app/BitcoinAgent/local_cli.py` work without AWS

### Memory
- [x] Strategies: SEMANTIC + USER_PREFERENCE + SUMMARIZATION, 30-day expiry
- [x] Invoke clients persist a UUID session in `~/.bitcoin-agent/session.json`
- [ ] After deploy, run `scripts/after_deploy.sh` and invoke twice (wait 5–30s) to confirm long-term recall

### Gateway / policy
- [x] `BitcoinGateway` + `WebSearch` connector
- [x] Policy engine attached in LOG_ONLY
- [x] `scripts/after_deploy.sh` fills `GATEWAY_ARN` in the Cedar template
- [ ] Review `.local/allow_read_tools.cedar`, then `agentcore add policy --name allow_read_tools --engine BitcoinPolicy --source .local/allow_read_tools.cedar`
- [ ] Review `agentcore logs --runtime BitcoinAgent --since 1h --query policy` before ENFORCE

### Observability and quality
- [x] OTEL instrumentation enabled
- [x] Custom evaluator `BitcoinAccuracy` plus built-in Helpfulness, GoalSuccessRate, ToolSelectionAccuracy, Refusal
- [x] Online eval `production_monitor` at 5% sampling
- [ ] After first deploy: `aws logs put-retention-policy --log-group-name /aws/bedrock-agentcore/runtimes/<AGENT_ID>-DEFAULT --retention-in-days 30`
- [ ] Run `scripts/quality-gate.sh` in CI after an invoke + 15s wait

### Sessions
- [x] Idle timeout 900s, max lifetime 7200s (interactive chat)
- [x] Python/TS clients reuse one `runtimeSessionId` until `--new-session`
- [ ] Call `StopRuntimeSession` when a chat is done if you create many short sessions

### Deploy

```bash
cd BitcoinAgent
agentcore deploy
./scripts/after_deploy.sh
set -a && source .local/deploy.env && set +a
python3 clients/python/invoke_agent.py "My name is Alex and I work on Bitcoin Core RPC tests"
# wait, then (same session file):
python3 clients/python/invoke_agent.py "What do you know about me?"
```

Memory, gateway URLs, and online evals are not available under `agentcore dev`.
Local notes still work there.
