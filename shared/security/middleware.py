"""
FastAPI security dependencies for ParkNexus A2A.

This module validates:
- Authorization bearer token
- X-Agent-Id
- X-Request-Id
- X-Timestamp
- X-Signature
- HMAC request body signature
"""

from fastapi import HTTPException, Request

from shared.security.audit import audit_event
from shared.security.auth import validate_bearer_token

from shared.config.security import (
    get_a2a_shared_secret,
    get_allowed_agent_tokens,
    get_max_clock_skew_seconds,
)

from shared.security.constants import (
    AGENT_ID_HEADER,
    AUTH_HEADER,
    REQUEST_ID_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
)
from shared.security.signing import validate_timestamp, verify_signature


async def require_secure_a2a_request(request: Request) -> dict:
    """
    Validate secured A2A request.

    Returns:
        Security context dictionary.

    Raises:
        HTTPException when validation fails.
    """
    headers = request.headers

    source_agent = headers.get(AGENT_ID_HEADER)
    request_id = headers.get(REQUEST_ID_HEADER)
    timestamp = headers.get(TIMESTAMP_HEADER)
    signature = headers.get(SIGNATURE_HEADER)
    authorization = headers.get(AUTH_HEADER)

    if not source_agent or not request_id or not timestamp or not signature:
        audit_event(
            event_type="a2a_auth_failed",
            source_agent=source_agent,
            request_id=request_id,
            status="missing_headers",
        )
        raise HTTPException(status_code=401, detail="Missing required A2A security headers")

    allowed_tokens = get_allowed_agent_tokens()

    if not validate_bearer_token(source_agent, authorization, allowed_tokens):
        audit_event(
            event_type="a2a_auth_failed",
            source_agent=source_agent,
            request_id=request_id,
            status="invalid_token",
        )
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    if not validate_timestamp(timestamp, get_max_clock_skew_seconds()):
        audit_event(
            event_type="a2a_auth_failed",
            source_agent=source_agent,
            request_id=request_id,
            status="invalid_timestamp",
        )
        raise HTTPException(status_code=401, detail="Invalid or expired timestamp")

    body = await request.body()

    if not verify_signature(
        secret=get_a2a_shared_secret(),
        agent_id=source_agent,
        request_id=request_id,
        timestamp=timestamp,
        body=body,
        received_signature=signature,
    ):
        audit_event(
            event_type="a2a_auth_failed",
            source_agent=source_agent,
            request_id=request_id,
            status="invalid_signature",
        )
        raise HTTPException(status_code=401, detail="Invalid A2A signature")

    audit_event(
        event_type="a2a_auth_success",
        source_agent=source_agent,
        request_id=request_id,
        status="success",
    )

    return {
        "source_agent": source_agent,
        "request_id": request_id,
    }


if __name__ == "__main__":
    """
    Manual test:
        python -m shared.security.middleware
    """
    print("Security middleware module loaded successfully")
