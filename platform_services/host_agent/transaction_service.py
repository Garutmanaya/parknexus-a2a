"""Persistent user transaction history for Host Agent."""

from sqlalchemy.orm import Session

from platform_services.registry_agent.database import PlatformSessionLocal, create_platform_tables
from platform_services.registry_agent.models import UserTransactionModel, utc_now
from shared.logging.logger import get_logger

logger = get_logger(__name__)


def _session() -> Session:
    create_platform_tables()
    return PlatformSessionLocal()


def record_transaction(
    user_id: str,
    transaction_type: str,
    status: str,
    provider_url: str,
    provider_agent: str | None = None,
    slot_code: str | None = None,
    hold_id: str | None = None,
    reservation_id: str | None = None,
    details: dict | None = None,
) -> dict:
    logger.info("transaction_record_started user_id=%s type=%s status=%s slot_code=%s hold_id=%s reservation_id=%s", user_id, transaction_type, status, slot_code, hold_id, reservation_id)
    db = _session()
    try:
        model = UserTransactionModel(
            user_id=user_id,
            transaction_type=transaction_type,
            status=status,
            provider_agent=provider_agent,
            provider_url=provider_url,
            slot_code=slot_code,
            hold_id=hold_id,
            reservation_id=reservation_id,
            details=details or {},
        )
        db.add(model); db.commit(); db.refresh(model)
        logger.info("transaction_record_completed transaction_id=%s", model.transaction_id)
        return transaction_to_dict(model)
    finally:
        db.close()


def update_transaction_status_by_hold(hold_id: str, status: str, details: dict | None = None) -> None:
    db = _session()
    try:
        rows = db.query(UserTransactionModel).filter(UserTransactionModel.hold_id == hold_id).all()
        for row in rows:
            row.status = status
            row.updated_at = utc_now()
            if details:
                row.details = {**(row.details or {}), **details}
        db.commit()
        logger.info("transaction_status_updated_by_hold hold_id=%s status=%s count=%s", hold_id, status, len(rows))
    finally:
        db.close()


def update_transaction_status_by_slot(provider_url: str, slot_code: str, status: str, details: dict | None = None) -> None:
    db = _session()
    try:
        rows = db.query(UserTransactionModel).filter(UserTransactionModel.provider_url == provider_url, UserTransactionModel.slot_code == slot_code).all()
        for row in rows:
            row.status = status
            row.updated_at = utc_now()
            if details:
                row.details = {**(row.details or {}), **details}
        db.commit()
        logger.info("transaction_status_updated_by_slot provider_url=%s slot_code=%s status=%s count=%s", provider_url, slot_code, status, len(rows))
    finally:
        db.close()


def list_transactions(user_id: str | None = None, limit: int = 25) -> list[dict]:
    db = _session()
    try:
        query = db.query(UserTransactionModel).order_by(UserTransactionModel.created_at.desc())
        if user_id:
            query = query.filter(UserTransactionModel.user_id == user_id)
        rows = query.limit(limit).all()
        logger.info("transaction_list_completed user_id=%s count=%s", user_id, len(rows))
        return [transaction_to_dict(row) for row in rows]
    finally:
        db.close()


def transaction_to_dict(model: UserTransactionModel) -> dict:
    return {
        "transaction_id": model.transaction_id,
        "user_id": model.user_id,
        "transaction_type": model.transaction_type,
        "status": model.status,
        "provider_agent": model.provider_agent,
        "provider_url": model.provider_url,
        "slot_code": model.slot_code,
        "hold_id": model.hold_id,
        "reservation_id": model.reservation_id,
        "details": model.details or {},
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }
