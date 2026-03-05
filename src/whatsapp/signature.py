"""Webhook signature validation for WhatsApp Cloud API.

Meta signs webhook payloads with HMAC-SHA256 using the App Secret.
The signature is sent in the X-Hub-Signature-256 header.
"""

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def validate_signature(
    payload: bytes, signature_header: str | None, app_secret: str,
) -> bool:
    """Validate the X-Hub-Signature-256 header against the request body.

    Args:
        payload: Raw request body bytes.
        signature_header: Value of X-Hub-Signature-256 header (format: "sha256=<hex>").
        app_secret: The WhatsApp App Secret used as the HMAC key.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header")
        return False

    if not signature_header.startswith("sha256="):
        logger.warning("Invalid signature format: %s", signature_header[:20])
        return False

    expected_signature = signature_header[7:]
    computed = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed, expected_signature):
        logger.warning("Webhook signature mismatch")
        return False

    return True
