import hashlib
import hmac
import re
import secrets

_PBKDF2_ITERATIONS = 600_000
_ALPHANUM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

_NAME_PATTERN = re.compile(r"\b([A-Za-z])([a-z]+)\b")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, expected_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        )
        return hmac.compare_digest(dk.hex(), expected_hex)
    except (ValueError, AttributeError):
        return False


def mask_pii(value: str | None) -> str | None:
    """Mask names/identifiers for logs. 'Ayush Singh' -> 'A. Singh'."""
    if not value:
        return value
    masked = _NAME_PATTERN.sub(r"\1.", value)
    return masked


def hash_identifier(value: str) -> str:
    """One-way hash for MRNs and other sensitive identifiers used in logs."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def redact_pii(payload: dict) -> dict:
    """Return a copy of a payload with PII fields redacted (recursive)."""
    sensitive_keys = {
        "name",
        "full_name",
        "first_name",
        "last_name",
        "phone",
        "email",
        "mrn",
        "address",
        "ssn",
        "birthdate",
        "date_of_birth",
    }

    def walk(value):
        if isinstance(value, dict):
            return {
                k: ("[REDACTED]" if k.lower() in sensitive_keys else walk(v))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    return walk(payload)
