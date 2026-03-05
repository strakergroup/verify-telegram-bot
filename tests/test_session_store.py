from src.session.store import SessionStore


class TestSessionStore:
    """Tests for the in-memory session store."""

    def test_set_and_get_api_key(self, session_store: SessionStore) -> None:
        session_store.set_api_key(12345, "test-key-abc")
        assert session_store.get_api_key(12345) == "test-key-abc"

    def test_get_nonexistent_user(self, session_store: SessionStore) -> None:
        assert session_store.get_api_key(99999) is None

    def test_is_authenticated(self, session_store: SessionStore) -> None:
        assert not session_store.is_authenticated(12345)
        session_store.set_api_key(12345, "key")
        assert session_store.is_authenticated(12345)

    def test_remove_existing(self, session_store: SessionStore) -> None:
        session_store.set_api_key(12345, "key")
        assert session_store.remove(12345) is True
        assert not session_store.is_authenticated(12345)

    def test_remove_nonexistent(self, session_store: SessionStore) -> None:
        assert session_store.remove(99999) is False

    def test_overwrite_key(self, session_store: SessionStore) -> None:
        session_store.set_api_key(12345, "old-key")
        session_store.set_api_key(12345, "new-key")
        assert session_store.get_api_key(12345) == "new-key"

    def test_multiple_users(self, session_store: SessionStore) -> None:
        session_store.set_api_key(1, "key-1")
        session_store.set_api_key(2, "key-2")
        assert session_store.get_api_key(1) == "key-1"
        assert session_store.get_api_key(2) == "key-2"
        session_store.remove(1)
        assert session_store.get_api_key(1) is None
        assert session_store.get_api_key(2) == "key-2"
