"""Main menu and help handler for WhatsApp bot."""

import logging

from ...whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

MENU_TEXT = (
    "*Straker Verify Bot*\n\n"
    "I can help you translate files using the Straker Verify API.\n\n"
    "*Available commands:*\n"
    "• *login* - Authenticate with your API key\n"
    "• *logout* - Remove your stored API key\n"
    "• *status* - Check authentication & balance\n"
    "• *translate* - Start a translation project\n"
    "• *ecfmg* - ECFMG certified translation order\n"
    "• *projects* - List recent projects\n"
    "• *project <id>* - View project details\n"
    "• *download <id>* - Download translated files\n"
    "• *cancel* - Cancel current operation\n"
    "• *menu* - Show this menu\n\n"
    "*Translation workflow:*\n"
    "1. Login with your API key\n"
    "2. Send *translate*\n"
    "3. Upload your file(s), then send *done*\n"
    "4. Search and select target languages\n"
    "5. Enter a project title\n"
    "6. Confirm and submit\n"
    "7. Use *download <project_id>* for translated files"
)


class MenuHandler:
    """Handles menu and help commands."""

    def __init__(self, wa_client: WhatsAppClient) -> None:
        self._wa = wa_client

    async def send_menu(self, phone: str) -> None:
        """Send the main menu to the user."""
        await self._wa.send_text(phone, MENU_TEXT)
