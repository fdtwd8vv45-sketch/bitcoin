# Production readiness — BitcoinAgent

Inbound auth is **AWS_IAM** (not `NONE`). The gateway uses AWS_IAM as well.
Policy engine `BitcoinPolicy` starts in **LOG_ONLY**. Switch to ENFORCE only
after you deploy, attach `policies/allow_read_tools.cedar.template` with the
real gateway ARN, and review decision logs.

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
- [ ] Register any future private API keys with `agentcore add credential` (never runtime env vars)

### Code quality
- [x] Input validation on prompt, userId, and sessionId
- [x] Errors return a generic message; details stay in logs
- [x] Memory and gateway are no-ops when their env vars are unset (`agentcore dev`)

### Memory
- [x] Strategies: SEMANTIC + USER_PREFERENCE + SUMMARIZATION, 30-day expiry
- [ ] After deploy, test with UUID session IDs (33+ characters)
- [ ] Wait 5–30 seconds between sessions before expecting long-term recall

### Gateway / policy
- [x] `BitcoinGateway` + `WebSearch` connector
- [x] Policy engine attached in LOG_ONLY
- [ ] Deploy, then add Cedar from `policies/allow_read_tools.cedar.template`
- [ ] Review `agentcore logs --runtime BitcoinAgent --since 1h --query policy` before ENFORCE

### Observability and quality
- [x] OTEL instrumentation enabled
- [x] Custom evaluator `BitcoinAccuracy` plus built-in Helpfulness, GoalSuccessRate, ToolSelectionAccuracy, Refusal
- [x] Online eval `production_monitor` at 5% sampling
- [ ] After first deploy: `aws logs put-retention-policy --log-group-name /aws/bedrock-agentcore/runtimes/<AGENT_ID>-DEFAULT --retention-in-days 30`
- [ ] Run `scripts/quality-gate.sh` in CI after an invoke + 15s wait

### Sessions
- [x] Idle timeout 900s, max lifetime 7200s (interactive chat)
- [ ] Reuse one `runtimeSessionId` per conversation
- [ ] Call `StopRuntimeSession` when a chat is done if you create many short sessions

### Deploy

```bash
cd BitcoinAgent
agentcore deploy
agentcore fetch access --name BitcoinAgent --type agent
agentcore fetch access --name BitcoinGateway
agentcore invoke "My name is Alex and I work on Bitcoin Core RPC tests"
# wait, then a new session:
agentcore invoke "What do you know about me?"
```

Memory, gateway URLs, and online evals are not available under `agentcore dev`.
