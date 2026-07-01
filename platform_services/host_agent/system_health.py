"""Environment health checks for ParkNexus demo/admin dashboard."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from sqlalchemy import create_engine, text

from shared.config.runtime import get_httpx_verify_tls
from shared.logging.logger import get_logger

logger = get_logger(__name__)


DEFAULT_COMPONENT_URLS = {
    "host_agent": "https://localhost:8030/health",
    "registry_agent": "https://localhost:8020/health",
    "provider_a": "https://localhost:8011/health",
    "provider_b": "https://localhost:8012/health",
    "ui_nginx": "http://localhost:8080/",
}


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _check_http(name: str, url: str, timeout: float = 3.0) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = httpx.get(url, timeout=timeout, verify=get_httpx_verify_tls())
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        healthy = 200 <= response.status_code < 300
        return {
            "name": name,
            "type": "http",
            "status": "healthy" if healthy else "unhealthy",
            "url": url,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "detail": "OK" if healthy else response.text[:300],
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.warning("system_health_http_check_failed name=%s url=%s error=%s", name, url, exc)
        return {
            "name": name,
            "type": "http",
            "status": "unhealthy",
            "url": url,
            "status_code": None,
            "latency_ms": latency_ms,
            "detail": str(exc),
        }


def _check_postgres() -> dict[str, Any]:
    started = time.perf_counter()
    host = _env("POSTGRES_HOST", "127.0.0.1")
    port = _env("POSTGRES_PORT", "5432")
    user = _env("POSTGRES_ADMIN_USER", "postgres")
    password = _env("POSTGRES_ADMIN_PASSWORD", "demo_postgres_password")
    database = _env("POSTGRES_ADMIN_DB", "postgres")
    url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"

    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            row = conn.execute(text("SELECT current_database(), current_user")).fetchone()
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "name": "postgres",
            "type": "database",
            "status": "healthy",
            "url": f"{host}:{port}/{database}",
            "status_code": None,
            "latency_ms": latency_ms,
            "detail": f"database={row[0]} user={row[1]}",
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.warning("system_health_postgres_check_failed error=%s", exc)
        return {
            "name": "postgres",
            "type": "database",
            "status": "unhealthy",
            "url": f"{host}:{port}/{database}",
            "status_code": None,
            "latency_ms": latency_ms,
            "detail": str(exc),
        }


def get_system_status() -> dict[str, Any]:
    """Return combined health state for admin dashboard."""
    logger.info("system_status_check_started")

    checks = [_check_postgres()]
    checks.extend(
        [
            _check_http("host_agent", _env("HOST_HEALTH_URL", DEFAULT_COMPONENT_URLS["host_agent"])),
            _check_http("registry_agent", _env("REGISTRY_HEALTH_URL", DEFAULT_COMPONENT_URLS["registry_agent"])),
            _check_http("provider_a", _env("PROVIDER_A_HEALTH_URL", DEFAULT_COMPONENT_URLS["provider_a"])),
            _check_http("provider_b", _env("PROVIDER_B_HEALTH_URL", DEFAULT_COMPONENT_URLS["provider_b"])),
            _check_http("ui_nginx", _env("UI_HEALTH_URL", DEFAULT_COMPONENT_URLS["ui_nginx"])),
        ]
    )

    overall = "healthy" if all(item["status"] == "healthy" for item in checks) else "degraded"
    result = {
        "status": overall,
        "healthy_count": sum(1 for item in checks if item["status"] == "healthy"),
        "total_count": len(checks),
        "components": checks,
        "checked_at_epoch": int(time.time()),
    }
    logger.info("system_status_check_completed status=%s healthy=%s total=%s", overall, result["healthy_count"], result["total_count"])
    return result


if __name__ == "__main__":
    import json

    print(json.dumps(get_system_status(), indent=2))
