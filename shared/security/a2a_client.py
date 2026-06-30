"""Secure A2A client helper."""

import json
import time
import uuid
import httpx

from shared.config.env import required_env
from shared.config.security import get_a2a_shared_secret
from shared.logging.logger import get_logger
from shared.security.constants import AGENT_ID_HEADER, AUTH_HEADER, REQUEST_ID_HEADER, SIGNATURE_HEADER, TIMESTAMP_HEADER
from shared.security.signing import sign_payload

logger = get_logger(__name__)


def build_signed_headers(body: bytes) -> dict[str, str]:
    agent_id = required_env("HOST_AGENT_ID")
    token = required_env("HOST_AGENT_TOKEN")
    request_id = str(uuid.uuid4())
    timestamp = str(int(time.time()))
    signature = sign_payload(get_a2a_shared_secret(), agent_id, request_id, timestamp, body)
    return {
        AUTH_HEADER: f"Bearer {token}",
        AGENT_ID_HEADER: agent_id,
        REQUEST_ID_HEADER: request_id,
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: signature,
        "Content-Type": "application/json",
    }


def post_a2a(url: str, payload: dict, verify_tls: bool, timeout: float = 10.0) -> dict:
    body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    headers = build_signed_headers(body)
    logger.info("a2a_client_post_started url=%s method=%s", url, payload.get("method"))
    logger.debug("a2a_client_payload=%s", payload)
    response = httpx.post(url, content=body, headers=headers, timeout=timeout, verify=verify_tls)
    logger.info("a2a_client_post_completed url=%s status_code=%s", url, response.status_code)
    response.raise_for_status()
    return response.json()
