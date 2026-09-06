/**
 * Call a deployed BitcoinAgent runtime with IAM SigV4.
 * Reuse runtimeSessionId across turns. Session IDs must be UUID-length (33+).
 */
import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from "@aws-sdk/client-bedrock-agentcore";

export async function invokeBitcoinAgent(options: {
  prompt: string;
  userId?: string;
  sessionId: string;
  region?: string;
  runtimeArn: string;
}): Promise<void> {
  if (options.sessionId.length < 33) {
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
        JSON.stringify({ prompt: options.prompt, userId: options.userId ?? "default-user" }),
      ),
      runtimeSessionId: options.sessionId,
    }),
  );
  const decoder = new TextDecoder();
  if (response.response) {
    for await (const chunk of response.response) {
      process.stdout.write(decoder.decode(chunk));
    }
  }
}
