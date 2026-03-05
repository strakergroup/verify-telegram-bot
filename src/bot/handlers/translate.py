import logging
import shutil
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from ...config import Settings
from ...db.connection import store_chat_id
from ...session.store import SessionStore
from ...verify.client import VerifyAPIError, VerifyClient
from ..keyboards import (
    CONFIRM_NO,
    CONFIRM_YES,
    LANG_CANCEL,
    LANG_DONE,
    LANG_PAGE_PREFIX,
    LANG_SELECT_PREFIX,
    build_confirm_keyboard,
    build_language_keyboard,
)
from ..states import TranslateStates

logger = logging.getLogger(__name__)

# Context keys for storing workflow data
CTX_FILES = "translate_files"
CTX_TEMP_DIR = "translate_temp_dir"
CTX_SELECTED_LANGS = "translate_selected_langs"
CTX_LANG_PAGE = "translate_lang_page"
CTX_LANG_SEARCH = "translate_lang_search"
CTX_TITLE = "translate_title"
CTX_LANG_MSG_ID = "translate_lang_msg_id"


def _cleanup_temp(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove temp directory and clear context data."""
    temp_dir = context.user_data.get(CTX_TEMP_DIR)  # type: ignore[union-attr]
    if temp_dir and Path(temp_dir).exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    cleanup_keys = (
        CTX_FILES, CTX_TEMP_DIR, CTX_SELECTED_LANGS,
        CTX_LANG_PAGE, CTX_TITLE, CTX_LANG_MSG_ID, CTX_LANG_SEARCH,
    )
    for key in cleanup_keys:
        context.user_data.pop(key, None)  # type: ignore[union-attr]


def create_translate_handlers(
    session_store: SessionStore,
    verify_client: VerifyClient,
    settings: Settings | None = None,
) -> dict:
    """Create translation workflow handler functions with injected dependencies."""

    async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /translate -- entry point for the translation workflow."""
        if not update.effective_message or not update.effective_user:
            return ConversationHandler.END

        user_id = update.effective_user.id
        if not session_store.is_authenticated(user_id):
            await update.effective_message.reply_text(
                "You need to be logged in first. Use /login to authenticate."
            )
            return ConversationHandler.END

        # Initialise workflow context
        temp_dir = tempfile.mkdtemp(prefix="verify_bot_")
        context.user_data[CTX_FILES] = []  # type: ignore[index]
        context.user_data[CTX_TEMP_DIR] = temp_dir  # type: ignore[index]
        context.user_data[CTX_SELECTED_LANGS] = set()  # type: ignore[index]
        context.user_data[CTX_LANG_PAGE] = 0  # type: ignore[index]
        context.user_data[CTX_LANG_SEARCH] = ""  # type: ignore[index]

        await update.effective_message.reply_text(
            "<b>Step 1/4: Upload Files</b>\n\n"
            "Send me the file(s) you want to translate.\n"
            "You can send multiple files one at a time.\n\n"
            "When you're done uploading, send /done.\n"
            "To cancel at any time, send /cancel.",
            parse_mode="HTML",
        )
        return TranslateStates.AWAITING_FILE

    async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle receiving a file during the upload step."""
        if not update.effective_message:
            return TranslateStates.AWAITING_FILE

        message = update.effective_message
        document = message.document

        if not document:
            await message.reply_text(
                "Please send a file as a document, or send /done when finished uploading."
            )
            return TranslateStates.AWAITING_FILE

        temp_dir = context.user_data.get(CTX_TEMP_DIR, "")  # type: ignore[union-attr]
        if not temp_dir:
            await message.reply_text("Session error. Please start over with /translate.")
            _cleanup_temp(context)
            return ConversationHandler.END

        file_name = document.file_name or f"file_{document.file_unique_id}"
        file_path = Path(temp_dir) / file_name

        status_msg = await message.reply_text(f"Downloading <code>{file_name}</code>...", parse_mode="HTML")
        try:
            tg_file = await document.get_file()
            await tg_file.download_to_drive(str(file_path))
            files: list = context.user_data.get(CTX_FILES, [])  # type: ignore[union-attr]
            files.append(str(file_path))
            context.user_data[CTX_FILES] = files  # type: ignore[index]

            await status_msg.edit_text(
                f"Received <code>{file_name}</code> ({len(files)} file(s) total).\n\n"
                "Send another file or /done to continue.",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to download file %s", file_name)
            await status_msg.edit_text(
                f"Failed to download <code>{file_name}</code>. Please try again.",
                parse_mode="HTML",
            )

        return TranslateStates.AWAITING_FILE

    async def done_uploading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /done -- transition from file upload to language selection."""
        if not update.effective_message:
            return ConversationHandler.END

        files: list = context.user_data.get(CTX_FILES, [])  # type: ignore[union-attr]
        if not files:
            await update.effective_message.reply_text(
                "You haven't uploaded any files yet. Send a file or /cancel to abort."
            )
            return TranslateStates.AWAITING_FILE

        # Fetch languages and show picker
        try:
            languages = await verify_client.get_languages()
        except Exception:
            logger.exception("Failed to fetch languages")
            await update.effective_message.reply_text(
                "Failed to fetch language list. Please try again later."
            )
            _cleanup_temp(context)
            return ConversationHandler.END

        context.user_data[CTX_LANG_PAGE] = 0  # type: ignore[index]
        selected: set = context.user_data.get(CTX_SELECTED_LANGS, set())  # type: ignore[union-attr]
        search_query: str = context.user_data.get(CTX_LANG_SEARCH, "")  # type: ignore[union-attr]
        keyboard = build_language_keyboard(languages, selected, page=0, search_query=search_query)

        msg = await update.effective_message.reply_text(
            f"<b>Step 2/4: Select Target Languages</b>\n\n"
            f"You uploaded <b>{len(files)}</b> file(s).\n"
            "Tap languages to select/deselect them.\n"
            "Type a language name to search, or use the navigation buttons.\n\n"
            "Tap <b>Done</b> when you've selected your target languages.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        context.user_data[CTX_LANG_MSG_ID] = msg.message_id  # type: ignore[index]
        return TranslateStates.AWAITING_LANGUAGES

    async def handle_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle inline keyboard callbacks for language selection."""
        query = update.callback_query
        if not query or not query.data:
            return TranslateStates.AWAITING_LANGUAGES

        await query.answer()
        data = query.data

        selected: set = context.user_data.get(CTX_SELECTED_LANGS, set())  # type: ignore[union-attr]
        page: int = context.user_data.get(CTX_LANG_PAGE, 0)  # type: ignore[union-attr]
        search_query: str = context.user_data.get(CTX_LANG_SEARCH, "")  # type: ignore[union-attr]

        if data == LANG_CANCEL:
            await query.edit_message_text("Translation cancelled.")
            _cleanup_temp(context)
            return ConversationHandler.END

        if data == LANG_DONE:
            if not selected:
                await query.answer("Please select at least one language.", show_alert=True)
                return TranslateStates.AWAITING_LANGUAGES
            # Move to title step
            languages = await verify_client.get_languages()
            lang_map = {lang.id: lang.name for lang in languages}
            selected_names = [lang_map.get(lid, lid) for lid in selected]

            await query.edit_message_text(
                f"<b>Step 3/4: Project Title</b>\n\n"
                f"Selected languages: {', '.join(selected_names)}\n\n"
                "Please enter a title for your translation project:",
                parse_mode="HTML",
            )
            return TranslateStates.AWAITING_TITLE

        if data.startswith(LANG_SELECT_PREFIX):
            lang_id = data[len(LANG_SELECT_PREFIX):]
            if lang_id in selected:
                selected.discard(lang_id)
            else:
                if len(selected) >= 50:
                    await query.answer("Maximum 50 languages allowed.", show_alert=True)
                    return TranslateStates.AWAITING_LANGUAGES
                selected.add(lang_id)
            context.user_data[CTX_SELECTED_LANGS] = selected  # type: ignore[index]

        if data.startswith(LANG_PAGE_PREFIX):
            page = int(data[len(LANG_PAGE_PREFIX):])
            context.user_data[CTX_LANG_PAGE] = page  # type: ignore[index]

        # Refresh the keyboard
        languages = await verify_client.get_languages()
        keyboard = build_language_keyboard(languages, selected, page=page, search_query=search_query)
        files: list = context.user_data.get(CTX_FILES, [])  # type: ignore[union-attr]
        try:
            await query.edit_message_text(
                f"<b>Step 2/4: Select Target Languages</b>\n\n"
                f"You uploaded <b>{len(files)}</b> file(s).\n"
                "Tap languages to select/deselect them.\n"
                "Type a language name to search, or use the navigation buttons.\n\n"
                "Tap <b>Done</b> when you've selected your target languages.",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception:
            pass  # Message unchanged, ignore edit error
        return TranslateStates.AWAITING_LANGUAGES

    async def handle_language_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle text input during language selection as a search query."""
        if not update.effective_message or not update.effective_message.text:
            return TranslateStates.AWAITING_LANGUAGES

        search_query = update.effective_message.text.strip()
        context.user_data[CTX_LANG_SEARCH] = search_query  # type: ignore[index]
        context.user_data[CTX_LANG_PAGE] = 0  # type: ignore[index]

        selected: set = context.user_data.get(CTX_SELECTED_LANGS, set())  # type: ignore[union-attr]
        languages = await verify_client.get_languages()
        keyboard = build_language_keyboard(languages, selected, page=0, search_query=search_query)

        files: list = context.user_data.get(CTX_FILES, [])  # type: ignore[union-attr]
        msg = await update.effective_message.reply_text(
            f"<b>Step 2/4: Select Target Languages</b>\n\n"
            f'Search: "{search_query}" | {len(files)} file(s) uploaded.\n'
            "Tap languages to select/deselect them.\n\n"
            "Tap <b>Done</b> when you've selected your target languages.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        context.user_data[CTX_LANG_MSG_ID] = msg.message_id  # type: ignore[index]
        return TranslateStates.AWAITING_LANGUAGES

    async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive the project title and show confirmation summary."""
        if not update.effective_message or not update.effective_message.text:
            return TranslateStates.AWAITING_TITLE

        title = update.effective_message.text.strip()
        if not title or len(title) > 255:
            await update.effective_message.reply_text(
                "Title must be between 1 and 255 characters. Please try again."
            )
            return TranslateStates.AWAITING_TITLE

        context.user_data[CTX_TITLE] = title  # type: ignore[index]

        # Build summary
        files: list = context.user_data.get(CTX_FILES, [])  # type: ignore[union-attr]
        selected: set = context.user_data.get(CTX_SELECTED_LANGS, set())  # type: ignore[union-attr]

        file_names = [Path(f).name for f in files]
        languages = await verify_client.get_languages()
        lang_map = {lang.id: lang.name for lang in languages}
        selected_names = [lang_map.get(lid, lid) for lid in selected]

        summary = (
            "<b>Step 4/4: Confirm Project</b>\n\n"
            f"<b>Title:</b> {title}\n"
            f"<b>Files:</b> {', '.join(file_names)}\n"
            f"<b>Target Languages:</b> {', '.join(selected_names)}\n\n"
            "Press <b>Confirm</b> to create the project or <b>Cancel</b> to abort."
        )

        await update.effective_message.reply_text(
            summary,
            parse_mode="HTML",
            reply_markup=build_confirm_keyboard(),
        )
        return TranslateStates.CONFIRM

    async def handle_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle the confirm/cancel callback for project creation."""
        query = update.callback_query
        if not query or not query.data or not update.effective_user:
            return ConversationHandler.END

        await query.answer()

        if query.data == CONFIRM_NO:
            await query.edit_message_text("Project cancelled.")
            _cleanup_temp(context)
            return ConversationHandler.END

        if query.data == CONFIRM_YES:
            user_id = update.effective_user.id
            api_key = session_store.get_api_key(user_id)
            if not api_key:
                await query.edit_message_text(
                    "Session expired. Please /login again."
                )
                _cleanup_temp(context)
                return ConversationHandler.END

            files: list = context.user_data.get(CTX_FILES, [])  # type: ignore[union-attr]
            selected: set = context.user_data.get(CTX_SELECTED_LANGS, set())  # type: ignore[union-attr]
            title: str = context.user_data.get(CTX_TITLE, "Untitled")  # type: ignore[union-attr]

            await query.edit_message_text("Creating project... Please wait.")

            # Build callback URI if webhook is configured
            callback_uri = None
            if settings and settings.webhook_base_url:
                callback_uri = f"{settings.webhook_base_url}/callback"

            try:
                result = await verify_client.create_project(
                    api_key=api_key,
                    files=[Path(f) for f in files],
                    language_ids=list(selected),
                    title=title,
                    confirmation_required=False,
                    callback_uri=callback_uri,
                )

                # Store the telegram chat_id in the DB for callback notifications
                chat_id = update.effective_user.id
                stored = await store_chat_id(result.project_id, chat_id)
                if stored:
                    logger.info("Stored chat_id=%d for project %s", chat_id, result.project_id)
                else:
                    logger.warning(
                        "Could not store chat_id for project %s (DB not configured or job not found)",
                        result.project_id,
                    )

                await query.edit_message_text(
                    "<b>Project Created Successfully!</b>\n\n"
                    f"<b>Project ID:</b> <code>{result.project_id}</code>\n"
                    "<b>Status:</b> Processing has started automatically.\n\n"
                    f"Use /download <code>{result.project_id}</code> to download "
                    "translated files once the project completes.\n"
                    "Use /projects to check the status.",
                    parse_mode="HTML",
                )
                logger.info(
                    "Project %s created by user %d with %d files and %d languages",
                    result.project_id, user_id, len(files), len(selected),
                )
            except VerifyAPIError as e:
                logger.error("Project creation failed for user %d: %s", user_id, e.detail)
                error_detail = str(e.detail)
                if "insufficient" in error_detail.lower() or "balance" in error_detail.lower():
                    await query.edit_message_text(
                        "<b>Insufficient Tokens</b>\n\n"
                        "You do not have enough tokens to create this project.\n"
                        "Please top up your balance and try again.\n\n"
                        "Use /balance to check your current balance.",
                        parse_mode="HTML",
                    )
                else:
                    await query.edit_message_text(
                        f"Failed to create project:\n{error_detail}\n\n"
                        "Please try again with /translate."
                    )
            except Exception:
                logger.exception("Unexpected error creating project for user %d", user_id)
                await query.edit_message_text(
                    "An unexpected error occurred. Please try again later."
                )

            _cleanup_temp(context)
            return ConversationHandler.END

        return TranslateStates.CONFIRM

    async def cancel_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the translation workflow at any point."""
        if update.effective_message:
            await update.effective_message.reply_text("Translation workflow cancelled.")
        _cleanup_temp(context)
        return ConversationHandler.END

    return {
        "translate_command": translate_command,
        "receive_file": receive_file,
        "done_uploading": done_uploading,
        "handle_language_callback": handle_language_callback,
        "handle_language_search": handle_language_search,
        "receive_title": receive_title,
        "handle_confirm_callback": handle_confirm_callback,
        "cancel_translate": cancel_translate,
    }
