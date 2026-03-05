import logging

from telegram import Update
from telegram.ext import ContextTypes

from ...session.store import SessionStore
from ...verify.client import VerifyAPIError, VerifyClient

logger = logging.getLogger(__name__)


def create_balance_handler(
    session_store: SessionStore,
    verify_client: VerifyClient,
) -> dict:
    """Create the balance handler function with injected dependencies."""

    async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /balance -- show the user's token balance."""
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        api_key = session_store.get_api_key(user_id)
        if not api_key:
            await update.effective_message.reply_text(
                "You need to be logged in. Use /login first."
            )
            return

        try:
            balance = await verify_client.get_balance(api_key)
            await update.effective_message.reply_text(
                f"<b>Your Token Balance:</b> {balance:,}",
                parse_mode="HTML",
            )
        except VerifyAPIError as e:
            logger.error("Failed to fetch balance for user %d: %s", user_id, e.detail)
            await update.effective_message.reply_text(
                "Failed to fetch your balance. Please try again later."
            )

    return {
        "balance_command": balance_command,
    }
