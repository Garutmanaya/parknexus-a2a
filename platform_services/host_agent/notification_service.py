"""Notification hooks for user booking events.

For this project, notifications are logged to file. This creates a stable
boundary where email/SMS providers can be added later without changing booking
workflow code.
"""

from shared.logging.logger import get_logger

logger = get_logger(__name__)


def send_booking_alert(user_id: str, event_type: str, payload: dict) -> None:
    """Send/log a user-facing booking alert."""
    logger.info(
        "booking_alert event_type=%s user_id=%s provider=%s slot_code=%s hold_id=%s reservation_id=%s price=%s duration=%s garage=%s",
        event_type,
        user_id,
        payload.get("provider_agent") or payload.get("provider_url"),
        payload.get("slot_code"),
        payload.get("hold_id"),
        payload.get("reservation_id"),
        payload.get("estimated_price") or payload.get("total_price"),
        payload.get("reserved_minutes") or payload.get("duration_minutes"),
        payload.get("garage_name") or payload.get("garage"),
    )
    logger.debug("booking_alert_payload=%s", payload)
