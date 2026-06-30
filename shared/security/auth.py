"""
Authentication helpers for ParkNexus A2A.

Current local security model:
- Bearer token validates caller identity
- HMAC signature validates request integrity

Later cloud model:
- replace or augment bearer tokens with OAuth2/OIDC or mTLS
- keep signed A2A requests for integrity
"""

from shared.security.constants import BEARER_PREFIX


def extract_bearer_token(authorization_header: str | None) -> str | None:
    """
    Extract bearer token from Authorization header.
    """
    if not authorization_header:
        return None

    if not authorization_header.startswith(BEARER_PREFIX):
        return None

    return authorization_header[len(BEARER_PREFIX):]


def validate_bearer_token(
    agent_id: str,
    authorization_header: str | None,
    allowed_agent_tokens: dict[str, str],
) -> bool:
    """
    Validate bearer token for an agent id.
    """
    token = extract_bearer_token(authorization_header)
    expected_token = allowed_agent_tokens.get(agent_id)

    if not token or not expected_token:
        return False

    return token == expected_token


if __name__ == "__main__":
    tokens = {"host_agent": "host-token"}

    assert validate_bearer_token(
        "host_agent",
        "Bearer host-token",
        tokens,
    )

    assert not validate_bearer_token(
        "host_agent",
        "Bearer wrong-token",
        tokens,
    )

    print("Auth utilities verified successfully")
