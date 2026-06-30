"""
Generate signed headers for local A2A testing.

Usage:
    python scripts/sign_a2a_request.py '{"jsonrpc":"2.0","id":"req-1","method":"search_slots","params":{"limit":3}}'
"""

import json
import sys
import time
import uuid

from dotenv import load_dotenv

from shared.security.config import get_a2a_shared_secret, required_env
from shared.security.signing import sign_payload


def main() -> None:
    """
    Print curl-ready headers for signed A2A request.
    """
    load_dotenv()

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/sign_a2a_request.py '<json-body>'")

    body_text = sys.argv[1]
    body = json.dumps(json.loads(body_text), separators=(",", ":")).encode("utf-8")

    agent_id = required_env("HOST_AGENT_ID")
    token = required_env("HOST_AGENT_TOKEN")
    request_id = str(uuid.uuid4())
    timestamp = str(int(time.time()))

    signature = sign_payload(
        secret=get_a2a_shared_secret(),
        agent_id=agent_id,
        request_id=request_id,
        timestamp=timestamp,
        body=body,
    )

    print(f"Authorization: Bearer {token}")
    print(f"X-Agent-Id: {agent_id}")
    print(f"X-Request-Id: {request_id}")
    print(f"X-Timestamp: {timestamp}")
    print(f"X-Signature: {signature}")
    print("")
    print(body.decode("utf-8"))


if __name__ == "__main__":
    main()
