import secrets
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.models.api_key import APIKey, DEFAULT_SCOPES

VALID_SCOPES = {"read:positions", "read:risk", "read:opportunities", "write:actions"}


def generate_raw_api_key() -> str:
    return f"mh_{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    return generate_password_hash(raw_key)


def verify_api_key(raw_key: str, api_key: APIKey) -> bool:
    return api_key.is_active is not False and check_password_hash(api_key.key_hash, raw_key)


def normalize_scopes(scopes):
    if not scopes:
        return list(DEFAULT_SCOPES)
    requested = set(scopes)
    invalid = requested - VALID_SCOPES
    if invalid:
        raise ValueError(f"Invalid scopes: {', '.join(sorted(invalid))}")
    return sorted(requested)


def touch_api_key(api_key: APIKey):
    api_key.last_used_at = datetime.now(timezone.utc)
