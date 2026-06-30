"""
HMAC signing utilities for ParkNexus A2A.

Signature protects:
- source agent identity
- request id
- timestamp
- request body

This prevents request tampering and helps reduce replay attacks.
"""

import hashlib
import hmac
import time


def build_signature_payload(
    agent_id: str,
    request_id: str,
    timestamp: str,
    body: bytes,
) -> bytes:
    """
    Build canonical payload to sign.
    """
    prefix = f"{agent_id}.{request_id}.{timestamp}.".encode("utf-8")
    return prefix + body


def sign_payload(
    secret: str,
    agent_id: str,
    request_id: str,
    timestamp: str,
    body: bytes,
) -> str:
    """
    Generate HMAC SHA256 signature.
    """
    payload = build_signature_payload(
        agent_id=agent_id,
        request_id=request_id,
        timestamp=timestamp,
        body=body,
    )

    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


def verify_signature(
    secret: str,
    agent_id: str,
    request_id: str,
    timestamp: str,
    body: bytes,
    received_signature: str,
) -> bool:
    """
    Verify HMAC SHA256 signature using constant-time comparison.
    """
    expected_signature = sign_payload(
        secret=secret,
        agent_id=agent_id,
        request_id=request_id,
        timestamp=timestamp,
        body=body,
    )

    return hmac.compare_digest(expected_signature, received_signature)


def validate_timestamp(timestamp: str, max_skew_seconds: int) -> bool:
    """
    Validate request timestamp against local time.

    Args:
        timestamp: Unix timestamp as string.
        max_skew_seconds: Allowed clock skew window.
    """
    try:
        request_time = int(timestamp)
    except ValueError:
        return False

    now = int(time.time())
    return abs(now - request_time) <= max_skew_seconds


if __name__ == "__main__":
    secret = "test_secret"
    agent_id = "host_agent"
    request_id = "req-001"
    timestamp = str(int(time.time()))
    body = b'{"method":"search_slots"}'

    signature = sign_payload(secret, agent_id, request_id, timestamp, body)

    assert verify_signature(secret, agent_id, request_id, timestamp, body, signature)
    assert validate_timestamp(timestamp, 300)

    print("Signing utilities verified successfully")
    print(f"signature={signature}")
