"""Provider-specific schema mapping and validation.

The Host Agent keeps canonical intent/search fields internally. Provider Agent Cards can
publish skill input schemas with `x-canonical` annotations. This mapper uses those
annotations to construct provider-specific payloads and validate them before A2A calls.
"""

from decimal import Decimal
from typing import Any

from shared.logging.logger import get_logger

logger = get_logger(__name__)


def get_skill(provider: dict, skill_id: str) -> dict | None:
    for skill in provider.get("skills", []):
        if skill.get("id") == skill_id:
            return skill
    return None


def _allowed_type(value: Any, schema_type: Any) -> bool:
    if schema_type is None:
        return True
    types = schema_type if isinstance(schema_type, list) else [schema_type]
    if value is None:
        return "null" in types
    if "boolean" in types and isinstance(value, bool):
        return True
    if "integer" in types and isinstance(value, int) and not isinstance(value, bool):
        return True
    if "number" in types and isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return True
    if "string" in types and isinstance(value, str):
        return True
    if "array" in types and isinstance(value, list):
        return True
    if "object" in types and isinstance(value, dict):
        return True
    return False


def validate_payload(payload: dict, schema: dict | None) -> None:
    if not schema:
        return
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    additional = schema.get("additionalProperties", True)

    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Missing required provider schema fields: {missing}")
    if additional is False:
        extra = [field for field in payload if field not in properties]
        if extra:
            raise ValueError(f"Unsupported provider schema fields: {extra}")
    for field, value in payload.items():
        field_schema = properties.get(field, {})
        if not _allowed_type(value, field_schema.get("type")):
            raise ValueError(f"Invalid type for field {field}: {value!r}")
        if "enum" in field_schema and value not in field_schema["enum"]:
            raise ValueError(f"Invalid enum value for field {field}: {value!r}")


def build_provider_payload(provider: dict, skill_id: str, canonical_params: dict) -> dict:
    skill = get_skill(provider, skill_id)
    schema = skill.get("input_schema") if skill else None
    properties = (schema or {}).get("properties", {})

    if not properties:
        payload = {key: value for key, value in canonical_params.items() if value is not None}
        validate_payload(payload, schema)
        return payload

    payload = {}
    for provider_field, field_schema in properties.items():
        canonical_name = field_schema.get("x-canonical", provider_field)
        if canonical_name in canonical_params:
            value = canonical_params[canonical_name]
            if value is not None:
                # JSON schemas may support number/string. Use string for Decimal to keep JSON safe.
                if isinstance(value, Decimal):
                    value = str(value)
                payload[provider_field] = value

    for required_field in (schema or {}).get("required", []):
        if required_field not in payload and required_field in canonical_params:
            payload[required_field] = canonical_params[required_field]

    validate_payload(payload, schema)
    logger.debug("provider_schema_payload_built provider=%s skill=%s payload=%s", provider.get("name"), skill_id, payload)
    return payload
