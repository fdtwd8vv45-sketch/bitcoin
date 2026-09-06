#!/usr/bin/env python3
"""Call a deployed BitcoinAgent runtime with IAM SigV4.

Session IDs are created and reused automatically so you do not have to
remember the UUID ceremony. Override with --session-id or BITCOIN_AGENT_SESSION.

    python clients/python/invoke_agent.py "What does getblockcount do?"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

_HERE = Path(__file__).resolve().parent
_APP = _HERE.parents[1] / "app" / "BitcoinAgent"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from agent_state import load_or_create_session  # noqa: E402


def _load_deploy_env() -> None:
    env_path = _HERE.parents[1] / ".local" / "deploy.env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


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
    _load_deploy_env()
    parser = argparse.ArgumentParser(description="Invoke deployed BitcoinAgent")
    parser.add_argument("prompt")
    parser.add_argument("--user-id", default=os.getenv("BITCOIN_AGENT_USER"))
    parser.add_argument("--session-id", default=os.getenv("BITCOIN_AGENT_SESSION"))
    parser.add_argument("--new-session", action="store_true", help="Start a fresh UUID session.")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--runtime-arn", default=os.getenv("AGENT_RUNTIME_ARN"))
    args = parser.parse_args()
    if not args.runtime_arn:
        raise SystemExit(
            "Set AGENT_RUNTIME_ARN, pass --runtime-arn, or run scripts/after_deploy.sh "
            "so BitcoinAgent/.local/deploy.env exists."
        )
    session = load_or_create_session(new_session=args.new_session, user_id=args.user_id)
    session_id = args.session_id or session["sessionId"]
    user_id = args.user_id or session["userId"]
    if len(session_id) < 33:
        raise SystemExit("session id must be at least 33 characters (use a UUID v4).")
    print(f"# session {session_id}  user {user_id}", file=sys.stderr)
    invoke(
        args.prompt,
        user_id=user_id,
        session_id=session_id,
        region=args.region,
        runtime_arn=args.runtime_arn,
    )


if __name__ == "__main__":
    main()
