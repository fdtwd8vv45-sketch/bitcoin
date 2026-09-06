#!/usr/bin/env python3
"""Call a deployed BitcoinAgent runtime with IAM SigV4.

Set AGENT_RUNTIME_ARN (from `agentcore fetch access --name BitcoinAgent`)
and AWS credentials before running. Reuse runtimeSessionId across turns.

    python clients/python/invoke_agent.py "What does getblockcount do?"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

import boto3
from botocore.exceptions import ClientError


def invoke(prompt: str, *, user_id: str, session_id: str, region: str, runtime_arn: str) -> None:
    client = boto3.client("bedrock-agentcore", region_name=region)
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt, "userId": user_id}).encode(),
            runtimeSessionId=session_id,
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "AccessDeniedException":
            raise SystemExit("Caller lacks bedrock-agentcore:InvokeAgentRuntime.") from exc
        if code == "ValidationException":
            raise SystemExit(f"Invalid request: {exc}") from exc
        if code == "ThrottlingException":
            raise SystemExit("Throttled. Retry with backoff.") from exc
        raise

    stream = response["response"]
    if hasattr(stream, "iter_lines"):
        for line in stream.iter_lines():
            if line:
                sys.stdout.write(line.decode())
                sys.stdout.flush()
        sys.stdout.write("\n")
        return
    content = stream.read()
    sys.stdout.write(content.decode() if isinstance(content, bytes) else str(content))
    sys.stdout.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke deployed BitcoinAgent")
    parser.add_argument("prompt")
    parser.add_argument("--user-id", default=os.getenv("BITCOIN_AGENT_USER", "default-user"))
    parser.add_argument("--session-id", default=os.getenv("BITCOIN_AGENT_SESSION") or str(uuid.uuid4()))
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--runtime-arn", default=os.getenv("AGENT_RUNTIME_ARN"))
    args = parser.parse_args()
    if not args.runtime_arn:
        raise SystemExit("Set AGENT_RUNTIME_ARN or pass --runtime-arn.")
    if len(args.session_id) < 33:
        raise SystemExit("session id must be at least 33 characters (use a UUID v4).")
    invoke(
        args.prompt,
        user_id=args.user_id,
        session_id=args.session_id,
        region=args.region,
        runtime_arn=args.runtime_arn,
    )


if __name__ == "__main__":
    main()
