/**
 * Call a deployed BitcoinAgent runtime with IAM SigV4.
 * Reuses ~/.bitcoin-agent/session.json so you do not mint a UUID every turn.
 *
 *   npx tsx clients/typescript/invoke_agent.ts "What does getblockcount do?"
 */
import { homedir } from "node:os";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from "@aws-sdk/client-bedrock-agentcore";

export type SessionRecord = { sessionId: string; userId: string };

function sessionFile(): string {
  const home = process.env.BITCOIN_AGENT_HOME ?? join(homedir(), ".bitcoin-agent");
  return join(home, "session.json");
}

export function loadOrCreateSession(options?: {
  newSession?: boolean;
  userId?: string;
}): SessionRecord {
  const path = sessionFile();
  let existing: Partial<SessionRecord> = {};
  if (!options?.newSession) {
    try {
      existing = JSON.parse(readFileSync(path, "utf8")) as SessionRecord;
    } catch {
      existing = {};
    }
  }
  const sessionId =
    existing.sessionId && existing.sessionId.length >= 33 ? existing.sessionId : randomUUID();
  const userId = options?.userId || existing.userId || "default-user";
  const record = { sessionId, userId };
  mkdirSync(join(path, ".."), { recursive: true });
  writeFileSync(path, JSON.stringify(record, null, 2) + "\n");
  return record;
}

export async function invokeBitcoinAgent(options: {
  prompt: string;
  userId?: string;
  sessionId?: string;
  region?: string;
  runtimeArn: string;
  newSession?: boolean;
}): Promise<void> {
  const session = loadOrCreateSession({
    newSession: options.newSession,
    userId: options.userId,
  });
  const sessionId = options.sessionId ?? session.sessionId;
  if (sessionId.length < 33) {
    throw new Error("sessionId must be at least 33 characters (use a UUID).");
  }
  const client = new BedrockAgentCoreClient({
    region: options.region ?? process.env.AWS_REGION ?? "us-east-1",
  });
  const response = await client.send(
    new InvokeAgentRuntimeCommand({
      agentRuntimeArn: options.runtimeArn,
      qualifier: "DEFAULT",
      payload: new TextEncoder().encode(
        JSON.stringify({ prompt: options.prompt, userId: options.userId ?? session.userId }),
      ),
      runtimeSessionId: sessionId,
    }),
  );
  const decoder = new TextDecoder();
  if (response.response) {
    for await (const chunk of response.response) {
      process.stdout.write(decoder.decode(chunk));
    }
  }
}

async function main(): Promise<void> {
  const args = process.argv.slice(2).filter((item) => item !== "--new-session");
  const newSession = process.argv.includes("--new-session");
  const prompt = args.join(" ").trim();
  const runtimeArn = process.env.AGENT_RUNTIME_ARN;
  if (!prompt) {
    throw new Error('Usage: npx tsx invoke_agent.ts "your question"');
  }
  if (!runtimeArn) {
    throw new Error("Set AGENT_RUNTIME_ARN (or source BitcoinAgent/.local/deploy.env).");
  }
  const session = loadOrCreateSession({ newSession });
  console.error(`# session ${session.sessionId}  user ${session.userId}`);
  await invokeBitcoinAgent({ prompt, runtimeArn, newSession });
}

const invokedDirectly = process.argv[1]?.includes("invoke_agent");
if (invokedDirectly) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
  });
}
