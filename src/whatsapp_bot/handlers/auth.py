"""Authentication handler: login, logout, status/balance for WhatsApp."""

import logging

from ...verify.client import VerifyAPIError, VerifyClient
from ...whatsapp.client import WhatsAppClient
from ..session_store import WhatsAppSessionStore
from ..states import ConversationState

logger = logging.getLogger(__name__)


class AuthHandler:
    """Handles login/logout/status flows."""

    def __init__(
        self,
        wa_client: WhatsAppClient,
        session_store: WhatsAppSessionStore,
        verify_client: VerifyClient,
    ) -> None:
        self._wa = wa_client
        self._session = session_store
        self._verify = verify_client

    async def handle_login_start(self, phone: str) -> None:
        """Prompt user to send their Verify API key."""
        if self._session.is_authenticated(phone):
            await self._wa.send_text(
                phone,
                "You are already logged in. Send *logout* first if you want to switch accounts.",
            )
            return
        await self._wa.send_text(
            phone,
            "Please send your Straker Verify API key.\n\n"
            "You can find it in the Verify dashboard under API Keys.\n"
            "Send *cancel* to abort.",
        )

    async def handle_receive_key(self, phone: str, text: str) -> ConversationState:
        """Validate the API key and store it."""
        api_key = text.strip()
        if not api_key:
            await self._wa.send_text(phone, "Please send your API key, or *cancel* to abort.")
            return ConversationState.AWAITING_API_KEY

        if len(api_key) < 10:
            await self._wa.send_text(phone, "That doesn't look like a valid API key. Please try again.")
            return ConversationState.AWAITING_API_KEY

        await self._wa.send_text(phone, "Validating your API key...")

        try:
            balance = await self._verify.get_balance(api_key)
            self._session.set_api_key(phone, api_key)
            await self._wa.send_text(
                phone,
                f"Login successful!\n\n"
                f"Your token balance: *{balance:,}* tokens.\n\n"
                "Send *menu* to see available commands.",
            )
            logger.info("User %s...%s authenticated successfully", phone[:4], phone[-4:])
            return ConversationState.IDLE
        except VerifyAPIError as e:
            logger.warning("API key validation failed for %s...%s: %s", phone[:4], phone[-4:], e.detail)
            await self._wa.send_text(
                phone,
                "Invalid API key. Please check your key and try again, or send *cancel* to abort.",
            )
            return ConversationState.AWAITING_API_KEY
        except Exception:
            logger.exception("Unexpected error during login for %s...%s", phone[:4], phone[-4:])
            await self._wa.send_text(phone, "An error occurred. Please try again later.")
            return ConversationState.IDLE

    async def handle_logout(self, phone: str) -> None:
        """Remove stored API key."""
        removed = self._session.remove(phone)
        if removed:
            await self._wa.send_text(phone, "You have been logged out. Send *login* to authenticate again.")
        else:
            await self._wa.send_text(phone, "You are not currently logged in.")

    async def handle_status(self, phone: str) -> None:
        """Show authentication status and balance."""
        api_key = self._session.get_api_key(phone)
        if not api_key:
            await self._wa.send_text(phone, "You are not logged in. Send *login* to authenticate.")
            return

        try:
            balance = await self._verify.get_balance(api_key)
            await self._wa.send_text(
                phone, f"Authenticated.\nToken balance: *{balance:,}* tokens.",
            )
        except VerifyAPIError:
            await self._wa.send_text(
                phone, "Your API key appears to be invalid. Please *login* again.",
            )
            self._session.remove(phone)
