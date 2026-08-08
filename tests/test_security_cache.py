from app.services.cache import CacheService
from app.services.security import (
    hash_identifier,
    hash_password,
    mask_pii,
    redact_pii,
    verify_password,
)


class TestSecurity:
    def test_password_hash_and_verify(self):
        stored = hash_password("s3cret-password")
        assert stored.startswith("pbkdf2_sha256$")
        assert verify_password("s3cret-password", stored) is True
        assert verify_password("wrong", stored) is False

    def test_verify_rejects_malformed_hash(self):
        assert verify_password("x", "not-a-hash") is False

    def test_mask_pii(self):
        assert mask_pii("Ayush Singh") == "A. S."
        assert mask_pii(None) is None

    def test_hash_identifier(self):
        assert len(hash_identifier("MRN-12345")) == 16
        assert hash_identifier("MRN-12345") == hash_identifier("MRN-12345")

    def test_redact_pii_nested(self):
        payload = {
            "patient": {"first_name": "Jane", "mrn": "M-1", "lab": {"value": 5.0}},
            "items": [{"email": "jane@x.com"}],
        }
        redacted = redact_pii(payload)
        assert redacted["patient"]["first_name"] == "[REDACTED]"
        assert redacted["patient"]["mrn"] == "[REDACTED]"
        assert redacted["patient"]["lab"]["value"] == 5.0
        assert redacted["items"][0]["email"] == "[REDACTED]"


class TestCache:
    def test_memory_fallback_get_set_delete(self):
        cache = CacheService(url="redis://127.0.0.1:1")  # unreachable -> fallback
        assert cache.using_redis is False
        cache.set("key", "value", ttl=60)
        assert cache.get("key") == "value"
        cache.delete("key")
        assert cache.get("key") is None

    def test_memory_fallback_ttl_expiry(self):
        cache = CacheService(url=None, default_ttl=3600)
        cache.set("key", "value", ttl=-1)
        assert cache.get("key") is None
