"""
Simple audit logging helpers for ParkNexus A2A.

For now this logs to stdout.
Later this can write to:
- PostgreSQL audit table
- CloudWatch
- OpenTelemetry
"""

from datetime import datetime, timezone


def audit_event(
    event_type: str,
    source_agent: str | None = None,
    target_agent: str | None = None,
    request_id: str | None = None,
    status: str | None = None,
    detail: str | None = None,
) -> None:
    """
    Emit structured audit event.
    """
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "source_agent": source_agent,
        "target_agent": target_agent,
        "request_id": request_id,
        "status": status,
        "detail": detail,
    }

    print(f"AUDIT {payload}")


if __name__ == "__main__":
    audit_event(
        event_type="security_test",
        source_agent="host_agent",
        target_agent="provider_agent",
        request_id="req-001",
        status="success",
        detail="audit logger working",
    )
