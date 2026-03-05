"""Translation workflow handler for WhatsApp: file upload, language selection, title, submit."""

import logging
import shutil
import tempfile
from pathlib import Path

from ...config import Settings
from ...db.connection import store_chat_id
from ...verify.client import VerifyAPIError, VerifyClient
from ...whatsapp.client import WhatsAppClient
from ...whatsapp.models import WebhookMessage
from ..session_store import WhatsAppSessionStore
from ..states import ConversationState

logger = logging.getLogger(__name__)

KEY_FILES = "translate_files"
KEY_TEMP_DIR = "translate_temp_dir"
KEY_SELECTED_LANGS = "translate_selected_langs"
KEY_TITLE = "translate_title"

MAX_LANGUAGES = 50
LANGUAGE_SEARCH_LIMIT = 10


class TranslateHandler:
    """Handles the multi-step translation workflow."""

    def __init__(
        self,
        wa_client: WhatsAppClient,
        session_store: WhatsAppSessionStore,
        verify_client: VerifyClient,
        settings: Settings | None = None,
    ) -> None:
        self._wa = wa_client
        self._session = session_store
        self._verify = verify_client
        self._settings = settings

    def _cleanup(self, phone: str) -> None:
        """Remove temp files and clear workflow data."""
        data = self._session.get_user_data(phone)
        temp_dir = data.get(KEY_TEMP_DIR)
        if temp_dir and Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        self._session.clear_user_data(phone)

    async def handle_start(self, phone: str) -> None:
        """Initialise the translation workflow."""
        temp_dir = tempfile.mkdtemp(prefix="verify_wa_")
        data = self._session.get_user_data(phone)
        data[KEY_FILES] = []
        data[KEY_TEMP_DIR] = temp_dir
        data[KEY_SELECTED_LANGS] = {}

        await self._wa.send_text(
            phone,
            "*Step 1/4: Upload Files*\n\n"
            "Send me the file(s) you want to translate.\n"
            "You can send multiple files one at a time.\n\n"
            "When you're done uploading, send *done*.\n"
            "Send *cancel* to abort.",
        )

    async def handle_file_or_text(
        self, phone: str, text: str, message: WebhookMessage,
    ) -> ConversationState:
        """Handle input during the file-upload step."""
        data = self._session.get_user_data(phone)

        if text.lower() == "done":
            files = data.get(KEY_FILES, [])
            if not files:
                await self._wa.send_text(phone, "No files uploaded yet. Send a file or *cancel*.")
                return ConversationState.AWAITING_FILE
            return await self._start_language_selection(phone, len(files))

        if message.type == "document" and message.document:
            return await self._save_file(phone, message.document.id, message.document.filename, data)

        if message.type == "image" and message.image:
            await self._wa.send_text(
                phone,
                "Please send files as *documents* (not images). "
                "Attach the file using the paperclip icon.",
            )
            return ConversationState.AWAITING_FILE

        await self._wa.send_text(phone, "Send a file as a document, or type *done* when finished.")
        return ConversationState.AWAITING_FILE

    async def _save_file(
        self, phone: str, media_id: str, filename: str, data: dict,
    ) -> ConversationState:
        """Download a file from WhatsApp and save to temp dir."""
        temp_dir = data.get(KEY_TEMP_DIR, "")
        if not temp_dir:
            await self._wa.send_text(phone, "Session error. Please start over with *translate*.")
            self._cleanup(phone)
            return ConversationState.IDLE

        try:
            file_bytes, _ = await self._wa.download_media(media_id)
            safe_name = filename or f"file_{media_id[:8]}"
            file_path = Path(temp_dir) / safe_name
            file_path.write_bytes(file_bytes)

            files: list = data.get(KEY_FILES, [])
            files.append(str(file_path))
            data[KEY_FILES] = files

            await self._wa.send_text(
                phone,
                f"Received *{safe_name}* ({len(files)} file(s) total).\n"
                "Send another file or *done* to continue.",
            )
        except Exception:
            logger.exception("Failed to download file %s for %s", media_id, phone)
            await self._wa.send_text(phone, "Failed to download that file. Please try again.")

        return ConversationState.AWAITING_FILE

    async def _start_language_selection(self, phone: str, file_count: int) -> ConversationState:
        """Transition to language selection step."""
        await self._wa.send_text(
            phone,
            f"*Step 2/4: Select Target Languages*\n\n"
            f"You uploaded *{file_count}* file(s).\n\n"
            "Type a language name to search (e.g. *french*).\n"
            "Or send *all* to see the first page of languages.\n\n"
            "After selecting languages, send *done* to continue.",
        )
        return ConversationState.AWAITING_LANGUAGES

    async def handle_language_input(
        self, phone: str, text: str, message: WebhookMessage,
    ) -> ConversationState:
        """Handle input during language selection."""
        data = self._session.get_user_data(phone)
        selected: dict = data.get(KEY_SELECTED_LANGS, {})

        if message.type == "interactive" and message.interactive and message.interactive.list_reply:
            lang_id = message.interactive.list_reply.id
            lang_name = message.interactive.list_reply.title

            if lang_id.startswith("lang_"):
                actual_id = lang_id[5:]
                if actual_id in selected:
                    del selected[actual_id]
                    await self._wa.send_text(
                        phone,
                        f"Removed *{lang_name}*.\n"
                        f"Selected: {len(selected)} language(s).\n"
                        "Search more or send *done*.",
                    )
                else:
                    if len(selected) >= MAX_LANGUAGES:
                        await self._wa.send_text(phone, f"Maximum {MAX_LANGUAGES} languages allowed.")
                        return ConversationState.AWAITING_LANGUAGES
                    selected[actual_id] = lang_name
                    await self._wa.send_text(
                        phone,
                        f"Selected *{lang_name}*.\n"
                        f"Total: {len(selected)} language(s).\n"
                        "Search more or send *done*.",
                    )
                data[KEY_SELECTED_LANGS] = selected
                return ConversationState.AWAITING_LANGUAGES

        if text.lower() == "done":
            if not selected:
                await self._wa.send_text(phone, "Please select at least one language first.")
                return ConversationState.AWAITING_LANGUAGES

            names = list(selected.values())
            await self._wa.send_text(
                phone,
                f"*Step 3/4: Project Title*\n\n"
                f"Selected languages: {', '.join(names)}\n\n"
                "Please enter a title for your translation project:",
            )
            return ConversationState.AWAITING_TITLE

        search = text.strip()
        if not search:
            await self._wa.send_text(phone, "Type a language name to search, or send *done* to continue.")
            return ConversationState.AWAITING_LANGUAGES

        try:
            languages = await self._verify.get_languages()
        except Exception:
            logger.exception("Failed to fetch languages")
            await self._wa.send_text(phone, "Failed to fetch languages. Please try again.")
            return ConversationState.AWAITING_LANGUAGES

        if search.lower() == "all":
            matches = languages[:LANGUAGE_SEARCH_LIMIT]
        else:
            matches = [
                lang for lang in languages if search.lower() in lang.name.lower()
            ][:LANGUAGE_SEARCH_LIMIT]

        if not matches:
            await self._wa.send_text(phone, f'No languages found matching "{search}". Try a different search.')
            return ConversationState.AWAITING_LANGUAGES

        rows = []
        for lang in matches:
            check = " [selected]" if lang.id in selected else ""
            rows.append({
                "id": f"lang_{lang.id}",
                "title": lang.name,
                "description": f"{lang.code}{check}",
            })

        sections = [{"title": "Languages", "rows": rows}]
        selected_info = f"\n{len(selected)} language(s) already selected." if selected else ""
        await self._wa.send_interactive_list(
            to=phone,
            body=f'Results for "{search}".{selected_info}\nTap a language to select/deselect.',
            button_text="View Languages",
            sections=sections,
            header="Select Languages",
        )
        return ConversationState.AWAITING_LANGUAGES

    async def handle_title_input(self, phone: str, text: str) -> ConversationState:
        """Handle project title input."""
        title = text.strip()
        if not title or len(title) > 255:
            await self._wa.send_text(phone, "Title must be between 1 and 255 characters. Please try again.")
            return ConversationState.AWAITING_TITLE

        data = self._session.get_user_data(phone)
        data[KEY_TITLE] = title

        files = data.get(KEY_FILES, [])
        selected: dict = data.get(KEY_SELECTED_LANGS, {})
        file_names = [Path(f).name for f in files]

        summary = (
            f"*Step 4/4: Confirm Project*\n\n"
            f"*Title:* {title}\n"
            f"*Files:* {', '.join(file_names)}\n"
            f"*Languages:* {', '.join(selected.values())}\n\n"
            "Press *Submit* to create the project or *Cancel* to abort."
        )

        await self._wa.send_interactive_buttons(
            to=phone,
            body=summary,
            buttons=[
                {"id": "confirm_yes", "title": "Submit"},
                {"id": "confirm_no", "title": "Cancel"},
            ],
            header="Confirm Project",
        )
        return ConversationState.AWAITING_CONFIRM

    async def handle_confirm_input(self, phone: str, text: str) -> ConversationState:
        """Handle the confirm/cancel response."""
        choice = text.lower().strip()

        if choice in ("confirm_no", "cancel", "no"):
            self._cleanup(phone)
            await self._wa.send_text(phone, "Project cancelled. Send *menu* to see commands.")
            return ConversationState.IDLE

        if choice not in ("confirm_yes", "submit", "yes"):
            await self._wa.send_text(phone, "Please tap *Submit* or *Cancel*.")
            return ConversationState.AWAITING_CONFIRM

        data = self._session.get_user_data(phone)
        api_key = self._session.get_api_key(phone)
        if not api_key:
            self._cleanup(phone)
            await self._wa.send_text(phone, "Session expired. Please *login* again.")
            return ConversationState.IDLE

        files = data.get(KEY_FILES, [])
        selected: dict = data.get(KEY_SELECTED_LANGS, {})
        title = data.get(KEY_TITLE, "Untitled")

        await self._wa.send_text(phone, "Creating project... Please wait.")

        # Build callback URI if webhook is configured
        callback_uri = None
        if self._settings and self._settings.webhook_base_url:
            callback_uri = f"{self._settings.webhook_base_url}/callback"

        try:
            result = await self._verify.create_project(
                api_key=api_key,
                files=[Path(f) for f in files],
                language_ids=list(selected.keys()),
                title=title,
                confirmation_required=False,
                callback_uri=callback_uri,
            )

            # Store WhatsApp phone in DB for callback notifications
            stored = await store_chat_id(
                result.project_id, 0, whatsapp_phone=phone,
            )
            if stored:
                logger.info("Stored whatsapp_phone=%s for project %s", phone, result.project_id)
            else:
                logger.warning(
                    "Could not store whatsapp_phone for project %s (DB not configured or job not found)",
                    result.project_id,
                )

            await self._wa.send_text(
                phone,
                f"*Project Created Successfully!*\n\n"
                f"*Project ID:* {result.project_id}\n"
                f"*Status:* Processing has started automatically.\n\n"
                f"Send *download {result.project_id}* to get translated files once complete.\n"
                "Send *projects* to check status.",
            )
            logger.info(
                "Project %s created by %s...%s with %d files and %d languages",
                result.project_id, phone[:4], phone[-4:], len(files), len(selected),
            )
        except VerifyAPIError as e:
            error_detail = str(e.detail)
            if "insufficient" in error_detail.lower() or "balance" in error_detail.lower():
                await self._wa.send_text(
                    phone,
                    "*Insufficient Tokens*\n\n"
                    "You do not have enough tokens to create this project.\n"
                    "Please top up your balance and try again.\n\n"
                    "Send *status* to check your balance.",
                )
            else:
                await self._wa.send_text(
                    phone,
                    f"Failed to create project: {error_detail}\n\nPlease try again with *translate*.",
                )
            logger.error("Project creation failed for %s: %s", phone, e.detail)
        except Exception:
            logger.exception("Unexpected error creating project for %s", phone)
            await self._wa.send_text(phone, "An unexpected error occurred. Please try again later.")

        self._cleanup(phone)
        return ConversationState.IDLE
