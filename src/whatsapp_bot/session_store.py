"""In-memory session store for WhatsApp users, keyed by phone number (E.164)."""

import logging

logger = logging.getLogger(__name__)


class WhatsAppSessionStore:
    """In-memory session store keyed by phone number (E.164 format).

    Stores Verify API keys for authenticated WhatsApp users.
    Designed for easy replacement with Redis in a future phase.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}
        self._user_data: dict[str, dict] = {}

    def set_api_key(self, phone: str, api_key: str) -> None:
        """Store API key for a WhatsApp phone number."""
        self._sessions[phone] = api_key
        logger.info("API key stored for phone %s...%s", phone[:4], phone[-4:])

    def get_api_key(self, phone: str) -> str | None:
        """Return stored API key or None."""
        return self._sessions.get(phone)

    def remove(self, phone: str) -> bool:
        """Remove session for a phone number. Returns True if existed."""
        existed = phone in self._sessions
        self._sessions.pop(phone, None)
        self._user_data.pop(phone, None)
        if existed:
            logger.info("Session removed for phone %s...%s", phone[:4], phone[-4:])
        return existed

    def is_authenticated(self, phone: str) -> bool:
        """Check if phone number has an active session."""
        return phone in self._sessions

    def get_user_data(self, phone: str) -> dict:
        """Get mutable user data dict for workflow state."""
        if phone not in self._user_data:
            self._user_data[phone] = {}
        return self._user_data[phone]

    def clear_user_data(self, phone: str) -> None:
        """Clear workflow data for a phone number."""
        self._user_data.pop(phone, None)
