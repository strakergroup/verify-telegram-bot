"""Tests for the WhatsApp SessionStore (phone-number keyed)."""

from src.whatsapp_bot.session_store import WhatsAppSessionStore


class TestWhatsAppSessionStore:
    def test_set_and_get_api_key(self) -> None:
        store = WhatsAppSessionStore()
        store.set_api_key("+6421000000", "key-abc")
        assert store.get_api_key("+6421000000") == "key-abc"

    def test_get_api_key_missing(self) -> None:
        store = WhatsAppSessionStore()
        assert store.get_api_key("+6421999999") is None

    def test_is_authenticated(self) -> None:
        store = WhatsAppSessionStore()
        assert not store.is_authenticated("+6421000000")
        store.set_api_key("+6421000000", "key-abc")
        assert store.is_authenticated("+6421000000")

    def test_remove_existing(self) -> None:
        store = WhatsAppSessionStore()
        store.set_api_key("+6421000000", "key-abc")
        assert store.remove("+6421000000") is True
        assert store.get_api_key("+6421000000") is None

    def test_remove_nonexistent(self) -> None:
        store = WhatsAppSessionStore()
        assert store.remove("+6421999999") is False

    def test_overwrite_api_key(self) -> None:
        store = WhatsAppSessionStore()
        store.set_api_key("+6421000000", "key-old")
        store.set_api_key("+6421000000", "key-new")
        assert store.get_api_key("+6421000000") == "key-new"

    def test_user_data_isolated(self) -> None:
        store = WhatsAppSessionStore()
        data_a = store.get_user_data("+6421000001")
        data_b = store.get_user_data("+6421000002")
        data_a["foo"] = "bar"
        assert "foo" not in data_b

    def test_clear_user_data(self) -> None:
        store = WhatsAppSessionStore()
        data = store.get_user_data("+6421000001")
        data["key"] = "value"
        store.clear_user_data("+6421000001")
        assert store.get_user_data("+6421000001") == {}

    def test_remove_clears_user_data(self) -> None:
        store = WhatsAppSessionStore()
        store.set_api_key("+6421000001", "key")
        data = store.get_user_data("+6421000001")
        data["workflow"] = "active"
        store.remove("+6421000001")
        assert store.get_user_data("+6421000001") == {}
