import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "<b>Welcome to Straker Verify Bot!</b>\n\n"
    "I can help you translate files using the Straker Verify API.\n\n"
    "<b>Getting started:</b>\n"
    "1. Use /login to authenticate with your Verify API key\n"
    "2. Use /translate to start a translation project\n"
    "3. Use /projects to view your recent projects\n\n"
    "Use /help to see all available commands."
)

HELP_TEXT = (
    "<b>Available Commands:</b>\n\n"
    "/start - Welcome message\n"
    "/help - Show this help message\n"
    "/login - Authenticate with your Verify API key\n"
    "/logout - Remove your stored API key\n"
    "/status - Show your authentication status\n"
    "/translate - Start a new translation project\n"
    "/projects - List your recent projects\n"
    "/project &lt;id&gt; - View project details\n"
    "/download &lt;id&gt; - Download translated files\n"
    "/balance - Check your token balance\n"
    "/ecfmg - Order an ECFMG certified translation\n"
    "/cancel - Cancel the current operation\n\n"
    "<b>Translation Workflow:</b>\n"
    "1. Login with your API key\n"
    "2. Start /translate\n"
    "3. Send your file(s)\n"
    "4. Select target language(s)\n"
    "5. Enter a project title\n"
    "6. Confirm and submit\n"
    "7. Use /download &lt;project_id&gt; to get translated files"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME_TEXT, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    if update.effective_message:
        await update.effective_message.reply_text(HELP_TEXT, parse_mode="HTML")
