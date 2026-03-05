import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from ...session.store import SessionStore
from ...verify.client import VerifyAPIError, VerifyClient
from ..states import AuthStates

logger = logging.getLogger(__name__)


def create_auth_handlers(
    session_store: SessionStore,
    verify_client: VerifyClient,
) -> dict:
    """Create auth handler functions with injected dependencies.

    Returns a dict of handler functions keyed by name.
    """

    async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /login -- ask the user for their API key."""
        if not update.effective_message or not update.effective_user:
            return ConversationHandler.END

        user_id = update.effective_user.id
        if session_store.is_authenticated(user_id):
            await update.effective_message.reply_text(
                "You are already logged in. Use /logout first if you want to switch accounts."
            )
            return ConversationHandler.END

        await update.effective_message.reply_text(
            "Please send me your Verify API key.\n\n"
            "<i>Your message will be deleted for security after I read it.</i>",
            parse_mode="HTML",
        )
        return AuthStates.AWAITING_API_KEY

    async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive and validate the user's API key."""
        if not update.effective_message or not update.effective_user:
            return ConversationHandler.END

        user_id = update.effective_user.id
        message = update.effective_message
        api_key = (message.text or "").strip()

        # Delete the message containing the API key for security
        try:
            await message.delete()
        except Exception:
            logger.warning("Could not delete API key message for user_id=%d", user_id)

        if not api_key:
            await message.reply_text("No API key received. Please try /login again.")
            return ConversationHandler.END

        # Validate by calling the balance endpoint
        status_msg = await message.reply_text("Validating your API key...")
        try:
            balance = await verify_client.get_balance(api_key)
            session_store.set_api_key(user_id, api_key)
            await status_msg.edit_text(
                f"Login successful!\n\nYour token balance: <b>{balance:,}</b>\n\n"
                "You can now use /translate to create a project.",
                parse_mode="HTML",
            )
            logger.info("User %d authenticated successfully", user_id)
        except VerifyAPIError as e:
            logger.warning("API key validation failed for user_id=%d: %s", user_id, e.detail)
            await status_msg.edit_text(
                "Invalid API key. Please check your key and try /login again."
            )
        except Exception:
            logger.exception("Unexpected error during login for user_id=%d", user_id)
            await status_msg.edit_text(
                "An error occurred while validating your key. Please try again later."
            )

        return ConversationHandler.END

    async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /logout -- remove the stored API key."""
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        if session_store.remove(user_id):
            await update.effective_message.reply_text("You have been logged out successfully.")
        else:
            await update.effective_message.reply_text("You are not currently logged in.")

    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status -- show authentication status."""
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        if not session_store.is_authenticated(user_id):
            await update.effective_message.reply_text(
                "You are not logged in. Use /login to authenticate."
            )
            return

        api_key = session_store.get_api_key(user_id)
        if not api_key:
            await update.effective_message.reply_text("Session error. Please /login again.")
            return

        try:
            balance = await verify_client.get_balance(api_key)
            await update.effective_message.reply_text(
                f"<b>Status:</b> Authenticated\n"
                f"<b>Token Balance:</b> {balance:,}",
                parse_mode="HTML",
            )
        except VerifyAPIError:
            session_store.remove(user_id)
            await update.effective_message.reply_text(
                "Your API key appears to be invalid. Session cleared.\n"
                "Please /login again."
            )

    async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the login conversation."""
        if update.effective_message:
            await update.effective_message.reply_text("Login cancelled.")
        return ConversationHandler.END

    return {
        "login_command": login_command,
        "receive_api_key": receive_api_key,
        "logout_command": logout_command,
        "status_command": status_command,
        "cancel_login": cancel_login,
    }
