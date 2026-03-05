"""Tests for WhatsApp MessageRouter state transitions and command dispatch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.verify.client import VerifyClient
from src.whatsapp.client import WhatsAppClient
from src.whatsapp.models import TextPayload, WebhookMessage
from src.whatsapp_bot.router import MessageRouter
from src.whatsapp_bot.session_store import WhatsAppSessionStore
from src.whatsapp_bot.states import ConversationState


def _make_text_message(text: str, from_number: str = "+6421000000") -> WebhookMessage:
    """Helper to create a text WebhookMessage."""
    return WebhookMessage(
        **{"from": from_number},
        id="msg_test",
        type="text",
        text=TextPayload(body=text),
    )


@pytest.fixture
def router() -> MessageRouter:
    wa = MagicMock(spec=WhatsAppClient)
    wa.send_text = AsyncMock()
    wa.mark_as_read = AsyncMock()
    wa.send_interactive_list = AsyncMock()
    wa.send_interactive_buttons = AsyncMock()

    session = WhatsAppSessionStore()
    verify = MagicMock(spec=VerifyClient)
    return MessageRouter(wa, session, verify)


class TestInitialState:
    def test_default_state_is_idle(self, router: MessageRouter) -> None:
        assert router.get_state("+6421000000") == ConversationState.IDLE

    def test_set_state(self, router: MessageRouter) -> None:
        router.set_state("+6421000000", ConversationState.AWAITING_API_KEY)
        assert router.get_state("+6421000000") == ConversationState.AWAITING_API_KEY


class TestMenuCommand:
    @pytest.mark.asyncio
    async def test_menu_resets_state(self, router: MessageRouter) -> None:
        router.set_state("+6421000000", ConversationState.AWAITING_FILE)
        msg = _make_text_message("menu")
        await router.route(msg)
        assert router.get_state("+6421000000") == ConversationState.IDLE


class TestLoginCommand:
    @pytest.mark.asyncio
    async def test_login_sets_awaiting_key(self, router: MessageRouter) -> None:
        msg = _make_text_message("login")
        with patch.object(router._auth, "handle_login_start", new_callable=AsyncMock):
            await router.route(msg)
        assert router.get_state("+6421000000") == ConversationState.AWAITING_API_KEY


class TestCancelCommand:
    @pytest.mark.asyncio
    async def test_cancel_resets_to_idle(self, router: MessageRouter) -> None:
        router.set_state("+6421000000", ConversationState.AWAITING_TITLE)
        msg = _make_text_message("cancel")
        await router.route(msg)
        assert router.get_state("+6421000000") == ConversationState.IDLE


class TestTranslateCommand:
    @pytest.mark.asyncio
    async def test_translate_requires_auth(self, router: MessageRouter) -> None:
        msg = _make_text_message("translate")
        await router.route(msg)
        router._wa.send_text.assert_called()
        call_args = router._wa.send_text.call_args
        assert "login" in call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_translate_with_auth(self, router: MessageRouter) -> None:
        router._session.set_api_key("+6421000000", "test-key")
        msg = _make_text_message("translate")
        with patch.object(router._translate, "handle_start", new_callable=AsyncMock):
            await router.route(msg)
        assert router.get_state("+6421000000") == ConversationState.AWAITING_FILE


class TestProjectsCommand:
    @pytest.mark.asyncio
    async def test_projects_requires_auth(self, router: MessageRouter) -> None:
        msg = _make_text_message("projects")
        await router.route(msg)
        router._wa.send_text.assert_called()
        call_args = router._wa.send_text.call_args
        assert "login" in call_args[0][1].lower()


class TestDownloadCommand:
    @pytest.mark.asyncio
    async def test_download_requires_auth(self, router: MessageRouter) -> None:
        msg = _make_text_message("download abc-123")
        await router.route(msg)
        router._wa.send_text.assert_called()
        call_args = router._wa.send_text.call_args
        assert "login" in call_args[0][1].lower()
