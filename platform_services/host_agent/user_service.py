"""User and admin helpers for Host Agent.

Admin password is loaded from .env. User passwords are stored as salted hashes.
This is suitable for the learning project. Production should use Cognito/OIDC.
"""

import hashlib
import hmac
import secrets
from sqlalchemy.orm import Session

from platform_services.registry_agent.database import PlatformSessionLocal, create_platform_tables
from platform_services.registry_agent.models import UserAccountModel, utc_now
from shared.config.env import optional_env
from shared.logging.logger import get_logger

logger = get_logger(__name__)


def get_admin_password() -> str:
    return optional_env("PARKNEXUS_ADMIN_PASSWORD", "admin123")


def validate_admin_login(username: str, password: str) -> bool:
    expected_user = optional_env("PARKNEXUS_ADMIN_USER", "admin")
    ok = username == expected_user and password == get_admin_password()
    logger.info("admin_login_attempt username=%s success=%s", username, ok)
    return ok


def _session() -> Session:
    create_platform_tables()
    return PlatformSessionLocal()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"{salt}:{digest}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash or ":" not in stored_hash:
        return False
    salt, digest = stored_hash.split(":", 1)
    candidate = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, digest)


def create_user(
    user_id: str,
    password: str,
    email: str,
    display_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    phone_number: str | None = None,
    address: str | None = None,
) -> dict:
    logger.info("user_create_started user_id=%s email=%s", user_id, email)
    db = _session()
    try:
        existing = db.query(UserAccountModel).filter(UserAccountModel.user_id == user_id).first()
        if existing:
            existing.display_name = display_name or user_id
            existing.email = email
            existing.first_name = first_name
            existing.last_name = last_name
            existing.phone_number = phone_number
            existing.address = address
            if password:
                existing.password_hash = hash_password(password)
            existing.is_active = True
            existing.updated_at = utc_now()
            db.commit(); db.refresh(existing)
            logger.info("user_create_updated user_id=%s", user_id)
            return user_to_dict(existing)

        model = UserAccountModel(
            user_id=user_id,
            password_hash=hash_password(password),
            display_name=display_name or user_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            address=address,
            is_active=True,
        )
        db.add(model); db.commit(); db.refresh(model)
        logger.info("user_create_completed user_id=%s", user_id)
        return user_to_dict(model)
    finally:
        db.close()


def update_user(
    user_id: str,
    password: str | None = None,
    email: str | None = None,
    display_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    phone_number: str | None = None,
    address: str | None = None,
    is_active: bool | None = None,
) -> dict:
    logger.info("user_update_started user_id=%s", user_id)
    db = _session()
    try:
        model = db.query(UserAccountModel).filter(UserAccountModel.user_id == user_id).first()
        if not model:
            raise RuntimeError(f"User not found: {user_id}")
        if password:
            model.password_hash = hash_password(password)
        if email is not None:
            model.email = email
        if display_name is not None:
            model.display_name = display_name
        if first_name is not None:
            model.first_name = first_name
        if last_name is not None:
            model.last_name = last_name
        if phone_number is not None:
            model.phone_number = phone_number
        if address is not None:
            model.address = address
        if is_active is not None:
            model.is_active = is_active
        model.updated_at = utc_now()
        db.commit(); db.refresh(model)
        logger.info("user_update_completed user_id=%s", user_id)
        return user_to_dict(model)
    finally:
        db.close()


def delete_user(user_id: str) -> dict:
    """Delete user account. Existing transaction history remains for audit/debug."""
    logger.info("user_delete_started user_id=%s", user_id)
    db = _session()
    try:
        model = db.query(UserAccountModel).filter(UserAccountModel.user_id == user_id).first()
        if not model:
            raise RuntimeError(f"User not found: {user_id}")
        payload = user_to_dict(model)
        db.delete(model)
        db.commit()
        logger.info("user_delete_completed user_id=%s", user_id)
        return payload
    finally:
        db.close()


def set_user_active(user_id: str, is_active: bool) -> dict:
    return update_user(user_id=user_id, is_active=is_active)


def validate_user_login(user_id: str, password: str) -> dict:
    logger.info("user_login_attempt user_id=%s", user_id)
    db = _session()
    try:
        model = db.query(UserAccountModel).filter(UserAccountModel.user_id == user_id).first()
        if not model or not model.is_active or not verify_password(password, model.password_hash):
            logger.info("user_login_failed user_id=%s", user_id)
            raise RuntimeError("Invalid user credentials")
        logger.info("user_login_success user_id=%s", user_id)
        return user_to_dict(model)
    finally:
        db.close()


def list_users() -> list[dict]:
    db = _session()
    try:
        models = db.query(UserAccountModel).order_by(UserAccountModel.created_at.desc()).all()
        logger.info("user_list_completed count=%s", len(models))
        return [user_to_dict(model) for model in models]
    finally:
        db.close()


def user_to_dict(model: UserAccountModel) -> dict:
    return {
        "user_id": model.user_id,
        "display_name": model.display_name,
        "first_name": model.first_name,
        "last_name": model.last_name,
        "email": model.email,
        "phone_number": model.phone_number,
        "address": model.address,
        "is_active": model.is_active,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }
