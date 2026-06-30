"""
Secure A2A client helper.

Adds:
- Bearer token
- X-Agent-Id
- X-Request-Id
- X-Timestamp
- X-Signature
"""

import json
import time
import uuid

import httpx


from shared.config.security import get_a2a_shared_secret
from shared.config.env import required_env
from shared.security.constants import (
    AGENT_ID_HEADER,
    AUTH_HEADER,
    REQUEST_ID_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
)
from shared.security.signing import sign_payload


def build_signed_headers(body: bytes) -> dict[str, str]:
    """
    Build signed A2A request headers for Host Agent.
    """
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

    return {
        AUTH_HEADER: f"Bearer {token}",
        AGENT_ID_HEADER: agent_id,
        REQUEST_ID_HEADER: request_id,
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: signature,
        "Content-Type": "application/json",
    }


def post_a2a(
    url: str,
    payload: dict,
    verify_tls: bool,
    timeout: float = 10.0,
) -> dict:
    """
    Send secure signed A2A POST request.
    """
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = build_signed_headers(body)

    response = httpx.post(
        url,
        content=body,
        headers=headers,
        timeout=timeout,
        verify=verify_tls,
    )
    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    print("Secure A2A client loaded successfully")
