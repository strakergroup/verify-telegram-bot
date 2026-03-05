"""Tests for webhook signature validation."""

import hashlib
import hmac

from src.whatsapp.signature import validate_signature

APP_SECRET = "test-app-secret-123"


def _make_signature(payload: bytes, secret: str) -> str:
    """Helper to compute valid signature header."""
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class TestValidateSignature:
    def test_valid_signature(self) -> None:
        payload = b'{"object":"whatsapp_business_account"}'
        sig = _make_signature(payload, APP_SECRET)
        assert validate_signature(payload, sig, APP_SECRET) is True

    def test_invalid_signature(self) -> None:
        payload = b'{"object":"whatsapp_business_account"}'
        assert validate_signature(payload, "sha256=0000bad0000", APP_SECRET) is False

    def test_missing_header(self) -> None:
        payload = b'{"object":"whatsapp_business_account"}'
        assert validate_signature(payload, None, APP_SECRET) is False

    def test_wrong_format(self) -> None:
        payload = b'{"object":"whatsapp_business_account"}'
        assert validate_signature(payload, "md5=abcdef", APP_SECRET) is False

    def test_empty_payload(self) -> None:
        payload = b""
        sig = _make_signature(payload, APP_SECRET)
        assert validate_signature(payload, sig, APP_SECRET) is True

    def test_tampered_payload(self) -> None:
        original = b'{"object":"whatsapp_business_account"}'
        sig = _make_signature(original, APP_SECRET)
        tampered = b'{"object":"tampered"}'
        assert validate_signature(tampered, sig, APP_SECRET) is False
