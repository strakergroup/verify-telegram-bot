import logging

logger = logging.getLogger(__name__)


class SessionStore:
    """In-memory session store keyed by Telegram user ID.

    Stores Verify API keys for authenticated users. Phase 1 uses an
    in-memory dict; Phase 2 can swap in a Redis-backed implementation.
    """

    def __init__(self) -> None:
        self._sessions: dict[int, str] = {}

    def set_api_key(self, user_id: int, api_key: str) -> None:
        """Store an API key for a Telegram user."""
        self._sessions[user_id] = api_key
        logger.info("Session stored for user_id=%d", user_id)

    def get_api_key(self, user_id: int) -> str | None:
        """Retrieve the stored API key for a user, or None if not logged in."""
        return self._sessions.get(user_id)

    def remove(self, user_id: int) -> bool:
        """Remove a user's session. Returns True if a session existed."""
        if user_id in self._sessions:
            del self._sessions[user_id]
            logger.info("Session removed for user_id=%d", user_id)
            return True
        return False

    def is_authenticated(self, user_id: int) -> bool:
        """Check if a user has an active session."""
        return user_id in self._sessions
