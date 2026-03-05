"""Message router: dispatches incoming WhatsApp messages to handlers based on conversation state."""

import logging

from ..config import Settings
from ..order.client import OrderClient
from ..verify.client import VerifyClient
from ..whatsapp.client import WhatsAppClient
from ..whatsapp.models import WebhookMessage
from .handlers.auth import AuthHandler
from .handlers.download import DownloadHandler
from .handlers.ecfmg import ECFMGHandler
from .handlers.menu import MenuHandler
from .handlers.projects import ProjectsHandler
from .handlers.translate import TranslateHandler
from .session_store import WhatsAppSessionStore
from .states import ConversationState

logger = logging.getLogger(__name__)

GLOBAL_COMMANDS = {
    "menu", "help", "login", "logout", "status", "translate",
    "projects", "project", "download", "balance", "cancel",
    "ecfmg",
}


class MessageRouter:
    """Routes incoming messages to the correct handler based on conversation state."""

    def __init__(
        self,
        wa_client: WhatsAppClient,
        session_store: WhatsAppSessionStore,
        verify_client: VerifyClient,
        settings: Settings | None = None,
        order_client: OrderClient | None = None,
    ) -> None:
        self._wa = wa_client
        self._session = session_store
        self._verify = verify_client
        self._states: dict[str, ConversationState] = {}

        self._menu = MenuHandler(wa_client)
        self._auth = AuthHandler(wa_client, session_store, verify_client)
        self._translate = TranslateHandler(wa_client, session_store, verify_client, settings)
        self._projects = ProjectsHandler(wa_client, session_store, verify_client)
        self._download = DownloadHandler(wa_client, session_store, verify_client)
        self._ecfmg: ECFMGHandler | None = None
        if order_client:
            self._ecfmg = ECFMGHandler(wa_client, session_store, order_client, settings)

    def get_state(self, phone: str) -> ConversationState:
        return self._states.get(phone, ConversationState.IDLE)

    def set_state(self, phone: str, state: ConversationState) -> None:
        self._states[phone] = state

    async def route(self, message: WebhookMessage) -> None:
        """Route a single incoming message to the appropriate handler."""
        phone = message.from_
        if not phone:
            return

        try:
            await self._wa.mark_as_read(message.id)
        except Exception:
            logger.debug("Failed to mark message %s as read", message.id)

        text = ""
        if message.type == "text" and message.text:
            text = message.text.body.strip()
        elif message.type == "interactive" and message.interactive:
            if message.interactive.button_reply:
                text = message.interactive.button_reply.id
            elif message.interactive.list_reply:
                text = message.interactive.list_reply.id

        command = text.lower().split()[0] if text else ""
        current_state = self.get_state(phone)

        if command in GLOBAL_COMMANDS:
            await self._handle_command(phone, command, text, message)
            return

        await self._handle_state(phone, current_state, text, message)

    async def _handle_command(
        self, phone: str, command: str, text: str, message: WebhookMessage,
    ) -> None:
        """Handle a recognised global command."""
        if command in ("menu", "help"):
            self.set_state(phone, ConversationState.IDLE)
            self._session.clear_user_data(phone)
            await self._menu.send_menu(phone)

        elif command == "login":
            self.set_state(phone, ConversationState.AWAITING_API_KEY)
            await self._auth.handle_login_start(phone)

        elif command == "logout":
            self.set_state(phone, ConversationState.IDLE)
            await self._auth.handle_logout(phone)

        elif command in ("status", "balance"):
            await self._auth.handle_status(phone)

        elif command == "translate":
            if not self._session.is_authenticated(phone):
                await self._wa.send_text(phone, "You need to login first. Send *login* to authenticate.")
                return
            self.set_state(phone, ConversationState.AWAITING_FILE)
            await self._translate.handle_start(phone)

        elif command == "projects":
            if not self._session.is_authenticated(phone):
                await self._wa.send_text(phone, "You need to login first. Send *login* to authenticate.")
                return
            await self._projects.handle_list(phone)

        elif command == "project":
            if not self._session.is_authenticated(phone):
                await self._wa.send_text(phone, "You need to login first. Send *login* to authenticate.")
                return
            parts = text.split(maxsplit=1)
            project_id = parts[1].strip() if len(parts) > 1 else ""
            await self._projects.handle_detail(phone, project_id)

        elif command == "download":
            if not self._session.is_authenticated(phone):
                await self._wa.send_text(phone, "You need to login first. Send *login* to authenticate.")
                return
            parts = text.split(maxsplit=1)
            project_id = parts[1].strip() if len(parts) > 1 else ""
            await self._download.handle_download(phone, project_id)

        elif command == "ecfmg":
            if not self._session.is_authenticated(phone):
                await self._wa.send_text(phone, "You need to login first. Send *login* to authenticate.")
                return
            if not self._ecfmg:
                await self._wa.send_text(phone, "ECFMG ordering is not configured.")
                return
            self.set_state(phone, ConversationState.ECFMG_FIRSTNAME)
            await self._ecfmg.handle_start(phone)

        elif command == "cancel":
            self.set_state(phone, ConversationState.IDLE)
            self._session.clear_user_data(phone)
            await self._wa.send_text(phone, "Operation cancelled. Send *menu* to see available commands.")

    async def _handle_state(
        self, phone: str, state: ConversationState, text: str, message: WebhookMessage,
    ) -> None:
        """Handle message based on the current conversation state."""
        if state == ConversationState.IDLE:
            await self._menu.send_menu(phone)

        elif state == ConversationState.AWAITING_API_KEY:
            new_state = await self._auth.handle_receive_key(phone, text)
            self.set_state(phone, new_state)

        elif state == ConversationState.AWAITING_FILE:
            new_state = await self._translate.handle_file_or_text(phone, text, message)
            self.set_state(phone, new_state)

        elif state == ConversationState.AWAITING_LANGUAGES:
            new_state = await self._translate.handle_language_input(phone, text, message)
            self.set_state(phone, new_state)

        elif state == ConversationState.AWAITING_TITLE:
            new_state = await self._translate.handle_title_input(phone, text)
            self.set_state(phone, new_state)

        elif state == ConversationState.AWAITING_CONFIRM:
            new_state = await self._translate.handle_confirm_input(phone, text)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_FIRSTNAME and self._ecfmg:
            new_state = await self._ecfmg.handle_firstname(phone, text)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_LASTNAME and self._ecfmg:
            new_state = await self._ecfmg.handle_lastname(phone, text)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_EMAIL and self._ecfmg:
            new_state = await self._ecfmg.handle_email(phone, text)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_PHONE and self._ecfmg:
            new_state = await self._ecfmg.handle_phone(phone, text)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_SOURCE_LANG and self._ecfmg:
            new_state = await self._ecfmg.handle_source_lang(phone, text, message)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_COUNTRY and self._ecfmg:
            new_state = await self._ecfmg.handle_country(phone, text, message)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_FILE and self._ecfmg:
            new_state = await self._ecfmg.handle_file(phone, text, message)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_TERMS and self._ecfmg:
            new_state = await self._ecfmg.handle_terms(phone, text, message)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_NOTES and self._ecfmg:
            new_state = await self._ecfmg.handle_notes(phone, text, message)
            self.set_state(phone, new_state)

        elif state == ConversationState.ECFMG_CONFIRM and self._ecfmg:
            new_state = await self._ecfmg.handle_confirm(phone, text, message)
            self.set_state(phone, new_state)

        else:
            await self._menu.send_menu(phone)
