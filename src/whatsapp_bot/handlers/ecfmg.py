"""ECFMG certified translation workflow handler for WhatsApp.

Collects personal details, language pair, country, file, terms acceptance,
and optional notes. Submits to the Order API (file/save + /job) and returns
the quote with a payment link.
"""

import asyncio
import logging
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from ...config import Settings
from ...order.client import OrderAPIError, OrderClient
from ...order.models import ECFMG_TARGET_LANG_CODE, ECFMG_TARGET_LANG_LABEL
from ...whatsapp.client import WhatsAppClient
from ...whatsapp.models import WebhookMessage
from ..session_store import WhatsAppSessionStore
from ..states import ConversationState

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

KEY_SESSION = "ecfmg_session"
KEY_FIRSTNAME = "ecfmg_firstname"
KEY_LASTNAME = "ecfmg_lastname"
KEY_EMAIL = "ecfmg_email"
KEY_PHONE = "ecfmg_phone"
KEY_SOURCE_LANG = "ecfmg_source_lang"
KEY_SOURCE_LANG_LABEL = "ecfmg_source_lang_label"
KEY_COUNTRY = "ecfmg_country"
KEY_COUNTRY_LABEL = "ecfmg_country_label"
KEY_FILE = "ecfmg_file"
KEY_TEMP_DIR = "ecfmg_temp_dir"
KEY_NOTES = "ecfmg_notes"

LANG_SEARCH_LIMIT = 10
COUNTRY_SEARCH_LIMIT = 10


class ECFMGHandler:
    """Handles the multi-step ECFMG workflow for WhatsApp."""

    def __init__(
        self,
        wa_client: WhatsAppClient,
        session_store: WhatsAppSessionStore,
        order_client: OrderClient,
        settings: Settings | None = None,
    ) -> None:
        self._wa = wa_client
        self._session = session_store
        self._order = order_client
        self._settings = settings

    def _cleanup(self, phone: str) -> None:
        data = self._session.get_user_data(phone)
        temp_dir = data.get(KEY_TEMP_DIR)
        if temp_dir and Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        self._session.clear_user_data(phone)

    async def handle_start(self, phone: str) -> None:
        temp_dir = tempfile.mkdtemp(prefix="verify_wa_ecfmg_")
        data = self._session.get_user_data(phone)
        data[KEY_SESSION] = str(uuid.uuid4()).upper()
        data[KEY_TEMP_DIR] = temp_dir

        await self._wa.send_text(
            phone,
            "*ECFMG Certified Translation*\n\n"
            "I'll guide you through the order process.\n"
            f"Target language is fixed to *{ECFMG_TARGET_LANG_LABEL}*.\n\n"
            "*Step 1/8: First Name*\n"
            "Please enter your first name:",
        )

    async def handle_firstname(self, phone: str, text: str) -> ConversationState:
        firstname = text.strip()
        if not firstname or len(firstname) > 100:
            await self._wa.send_text(phone, "Please enter a valid first name (1-100 characters).")
            return ConversationState.ECFMG_FIRSTNAME

        data = self._session.get_user_data(phone)
        data[KEY_FIRSTNAME] = firstname
        await self._wa.send_text(
            phone,
            "*Step 2/8: Last Name*\n"
            "Please enter your last name:",
        )
        return ConversationState.ECFMG_LASTNAME

    async def handle_lastname(self, phone: str, text: str) -> ConversationState:
        lastname = text.strip()
        if not lastname or len(lastname) > 100:
            await self._wa.send_text(phone, "Please enter a valid last name (1-100 characters).")
            return ConversationState.ECFMG_LASTNAME

        data = self._session.get_user_data(phone)
        data[KEY_LASTNAME] = lastname
        await self._wa.send_text(
            phone,
            "*Step 3/8: Email Address*\n"
            "Please enter your email address:",
        )
        return ConversationState.ECFMG_EMAIL

    async def handle_email(self, phone: str, text: str) -> ConversationState:
        email = text.strip()
        if not EMAIL_PATTERN.match(email):
            await self._wa.send_text(phone, "That doesn't look like a valid email. Please try again.")
            return ConversationState.ECFMG_EMAIL

        data = self._session.get_user_data(phone)
        data[KEY_EMAIL] = email
        await self._wa.send_text(
            phone,
            "*Step 4/8: Phone Number*\n"
            "Please enter your phone number:",
        )
        return ConversationState.ECFMG_PHONE

    async def handle_phone(self, phone: str, text: str) -> ConversationState:
        phone_num = text.strip()
        if not phone_num or len(phone_num) < 5:
            await self._wa.send_text(phone, "Please enter a valid phone number.")
            return ConversationState.ECFMG_PHONE

        data = self._session.get_user_data(phone)
        data[KEY_PHONE] = phone_num
        return await self._show_source_lang_list(phone)

    async def _show_source_lang_list(self, phone: str) -> ConversationState:
        try:
            languages = await self._order.get_ecfmg_languages()
        except Exception:
            logger.exception("Failed to fetch ECFMG languages")
            await self._wa.send_text(phone, "Failed to fetch languages. Please try again later.")
            self._cleanup(phone)
            return ConversationState.IDLE

        if not languages:
            await self._wa.send_text(phone, "No ECFMG languages available. Please try again later.")
            self._cleanup(phone)
            return ConversationState.IDLE

        rows = [
            {"id": f"ecfmg_sl_{lang.code}", "title": lang.display_name[:24]}
            for lang in languages[:LANG_SEARCH_LIMIT]
        ]
        sections = [{"title": "Source Languages", "rows": rows}]
        await self._wa.send_interactive_list(
            to=phone,
            body="Select the language of your document.",
            button_text="View Languages",
            sections=sections,
            header="Step 5/8: Source Language",
        )
        return ConversationState.ECFMG_SOURCE_LANG

    async def handle_source_lang(
        self, phone: str, text: str, message: WebhookMessage,
    ) -> ConversationState:
        if message.type == "interactive" and message.interactive and message.interactive.list_reply:
            item_id = message.interactive.list_reply.id
            if item_id.startswith("ecfmg_sl_"):
                lang_value = item_id[len("ecfmg_sl_"):]
                lang_label = message.interactive.list_reply.title
                data = self._session.get_user_data(phone)
                data[KEY_SOURCE_LANG] = lang_value
                data[KEY_SOURCE_LANG_LABEL] = lang_label
                return await self._show_country_list(phone, "")

        await self._wa.send_text(phone, "Please select a language from the list.")
        return ConversationState.ECFMG_SOURCE_LANG

    async def _show_country_list(
        self, phone: str, search: str,
    ) -> ConversationState:
        try:
            countries = await self._order.get_countries()
        except Exception:
            logger.exception("Failed to fetch countries")
            await self._wa.send_text(phone, "Failed to fetch countries. Please try again later.")
            self._cleanup(phone)
            return ConversationState.IDLE

        if search:
            filtered = [
                c for c in countries if search.lower() in c.display_name.lower()
            ][:COUNTRY_SEARCH_LIMIT]
        else:
            filtered = countries[:COUNTRY_SEARCH_LIMIT]

        if not filtered:
            await self._wa.send_text(
                phone,
                f'No countries found matching "{search}". Try a different search.',
            )
            return ConversationState.ECFMG_COUNTRY

        rows = [
            {"id": f"ecfmg_ctry_{c.id_str}", "title": c.display_name[:24]}
            for c in filtered
        ]
        sections = [{"title": "Countries", "rows": rows}]
        body = "Select your country."
        if search:
            body = f'Results for "{search}".\nTap a country to select.'
        await self._wa.send_interactive_list(
            to=phone,
            body=body,
            button_text="View Countries",
            sections=sections,
            header="Step 6/8: Country",
            footer="Type a country name to search",
        )
        return ConversationState.ECFMG_COUNTRY

    async def handle_country(
        self, phone: str, text: str, message: WebhookMessage,
    ) -> ConversationState:
        if message.type == "interactive" and message.interactive and message.interactive.list_reply:
            item_id = message.interactive.list_reply.id
            if item_id.startswith("ecfmg_ctry_"):
                country_value = item_id[len("ecfmg_ctry_"):]
                country_label = message.interactive.list_reply.title
                data = self._session.get_user_data(phone)
                data[KEY_COUNTRY] = country_value
                data[KEY_COUNTRY_LABEL] = country_label

                await self._wa.send_text(
                    phone,
                    f"Country: *{country_label}*\n\n"
                    "*Step 7/8: Upload Document*\n"
                    "Send me the document you need translated.\n"
                    "Send *cancel* to abort.",
                )
                return ConversationState.ECFMG_FILE

        if text:
            return await self._show_country_list(phone, text)

        await self._wa.send_text(phone, "Type a country name to search, or select from the list.")
        return ConversationState.ECFMG_COUNTRY

    async def handle_file(
        self, phone: str, text: str, message: WebhookMessage,
    ) -> ConversationState:
        if message.type == "document" and message.document:
            return await self._save_file(phone, message.document.id, message.document.filename)

        if message.type == "image" and message.image:
            await self._wa.send_text(
                phone,
                "Please send files as *documents* (not images). "
                "Attach the file using the paperclip icon.",
            )
            return ConversationState.ECFMG_FILE

        await self._wa.send_text(phone, "Please send a file as a document attachment.")
        return ConversationState.ECFMG_FILE

    async def _save_file(
        self, phone: str, media_id: str, filename: str,
    ) -> ConversationState:
        data = self._session.get_user_data(phone)
        temp_dir = data.get(KEY_TEMP_DIR, "")
        if not temp_dir:
            await self._wa.send_text(phone, "Session error. Please start over with *ecfmg*.")
            self._cleanup(phone)
            return ConversationState.IDLE

        try:
            file_bytes, _ = await self._wa.download_media(media_id)
            safe_name = filename or f"file_{media_id[:8]}"
            file_path = Path(temp_dir) / safe_name
            file_path.write_bytes(file_bytes)
            data[KEY_FILE] = str(file_path)

            await self._wa.send_interactive_buttons(
                to=phone,
                body=(
                    f"Received *{safe_name}*\n\n"
                    "*Step 8/8: Terms & Conditions*\n\n"
                    "By proceeding, you accept Straker's terms and conditions "
                    "and agree to receive communications about Straker's products and services.\n\n"
                    "Do you accept?"
                ),
                buttons=[
                    {"id": "ecfmg_terms_yes", "title": "Accept"},
                    {"id": "ecfmg_terms_no", "title": "Decline"},
                ],
                header="Terms & Conditions",
            )
            return ConversationState.ECFMG_TERMS
        except Exception:
            logger.exception("Failed to download file %s for %s", media_id, phone)
            await self._wa.send_text(phone, "Failed to download that file. Please try again.")
            return ConversationState.ECFMG_FILE

    async def handle_terms(
        self, phone: str, text: str, message: WebhookMessage,
    ) -> ConversationState:
        choice = text.lower().strip()

        if choice in ("ecfmg_terms_no", "decline", "no"):
            await self._wa.send_text(
                phone, "You must accept the terms to proceed. Order cancelled.",
            )
            self._cleanup(phone)
            return ConversationState.IDLE

        if choice in ("ecfmg_terms_yes", "accept", "yes"):
            await self._wa.send_interactive_buttons(
                to=phone,
                body=(
                    "Terms accepted.\n\n"
                    "*Additional Notes* (optional)\n"
                    "Enter any notes for the translator, or tap *Skip*."
                ),
                buttons=[
                    {"id": "ecfmg_notes_skip", "title": "Skip"},
                    {"id": "ecfmg_notes_cancel", "title": "Cancel"},
                ],
                header="Notes",
            )
            return ConversationState.ECFMG_NOTES

        await self._wa.send_text(phone, "Please tap *Accept* or *Decline*.")
        return ConversationState.ECFMG_TERMS

    async def handle_notes(
        self, phone: str, text: str, message: WebhookMessage,
    ) -> ConversationState:
        choice = text.lower().strip()

        if choice == "ecfmg_notes_cancel":
            self._cleanup(phone)
            await self._wa.send_text(phone, "Order cancelled. Send *menu* to see commands.")
            return ConversationState.IDLE

        data = self._session.get_user_data(phone)
        if choice == "ecfmg_notes_skip":
            data[KEY_NOTES] = ""
        else:
            data[KEY_NOTES] = text.strip()

        return await self._show_summary(phone)

    async def _show_summary(self, phone: str) -> ConversationState:
        data = self._session.get_user_data(phone)
        file_name = Path(data.get(KEY_FILE, "")).name
        summary = (
            "*Order Summary*\n\n"
            f"*Name:* {data.get(KEY_FIRSTNAME)} {data.get(KEY_LASTNAME)}\n"
            f"*Email:* {data.get(KEY_EMAIL)}\n"
            f"*Phone:* {data.get(KEY_PHONE)}\n"
            f"*From:* {data.get(KEY_SOURCE_LANG_LABEL)}\n"
            f"*To:* {ECFMG_TARGET_LANG_LABEL}\n"
            f"*Country:* {data.get(KEY_COUNTRY_LABEL)}\n"
            f"*File:* {file_name}\n"
        )
        notes = data.get(KEY_NOTES, "")
        if notes:
            summary += f"*Notes:* {notes}\n"

        await self._wa.send_interactive_buttons(
            to=phone,
            body=summary,
            buttons=[
                {"id": "ecfmg_submit", "title": "Order Now"},
                {"id": "ecfmg_cancel", "title": "Cancel"},
            ],
            header="Confirm Order",
        )
        return ConversationState.ECFMG_CONFIRM

    async def handle_confirm(
        self, phone: str, text: str, message: WebhookMessage,
    ) -> ConversationState:
        choice = text.lower().strip()

        if choice in ("ecfmg_cancel", "cancel", "no"):
            self._cleanup(phone)
            await self._wa.send_text(phone, "Order cancelled. Send *menu* to see commands.")
            return ConversationState.IDLE

        if choice not in ("ecfmg_submit", "order", "yes"):
            await self._wa.send_text(phone, "Please tap *Order Now* or *Cancel*.")
            return ConversationState.ECFMG_CONFIRM

        data = self._session.get_user_data(phone)
        file_path = Path(data.get(KEY_FILE, ""))
        session_token = data.get(KEY_SESSION, "")

        await self._wa.send_text(phone, "Submitting your order... Please wait.")

        try:
            upload_task = self._order.upload_file(
                file_path=file_path,
                session_token=session_token,
            )
            job_task = self._order.create_job(
                firstname=data.get(KEY_FIRSTNAME, ""),
                lastname=data.get(KEY_LASTNAME, ""),
                email=data.get(KEY_EMAIL, ""),
                phone=data.get(KEY_PHONE, ""),
                source_lang=data.get(KEY_SOURCE_LANG, ""),
                target_lang=ECFMG_TARGET_LANG_CODE,
                country=data.get(KEY_COUNTRY, ""),
                session_token=session_token,
                notes=data.get(KEY_NOTES, ""),
            )

            upload_result, job_result = await asyncio.gather(
                upload_task, job_task, return_exceptions=True,
            )

            if isinstance(upload_result, Exception):
                raise upload_result
            if isinstance(job_result, Exception):
                raise job_result

            quote = job_result.quotes[0] if job_result.quotes else None
            msg_parts = [
                "*ECFMG Order Submitted!*\n",
                f"*Job ID:* TJ{job_result.jobid}",
                f"*From:* {job_result.sl}",
                f"*To:* {job_result.tl}",
                f"*E-mail:* {job_result.emailto}",
                f"*File:* {file_path.name}",
            ]

            if quote:
                msg_parts.extend([
                    "",
                    f"*Price:* {quote.price} ({job_result.currency})",
                    f"*Subtotal:* {job_result.cSymbl} {quote.subtotal}",
                ])
                if quote.tax_name and quote.tax != "0.00":
                    msg_parts.append(f"*{quote.tax_name}:* {job_result.cSymbl} {quote.tax}")
                msg_parts.append(f"*Total:* {job_result.cSymbl}{quote.total}")
                if quote.paymentLink:
                    msg_parts.extend(["", f"Pay now: {quote.paymentLink}"])

            await self._wa.send_text(phone, "\n".join(msg_parts))
            logger.info(
                "ECFMG job %d created by %s...%s",
                job_result.jobid, phone[:4], phone[-4:],
            )
        except OrderAPIError as e:
            logger.error("ECFMG order failed for %s: %s", phone, e.detail)
            await self._wa.send_text(
                phone, f"Order failed: {e.detail}\n\nPlease try again with *ecfmg*.",
            )
        except Exception:
            logger.exception("Unexpected error during ECFMG order for %s", phone)
            await self._wa.send_text(
                phone, "An unexpected error occurred. Please try again later.",
            )

        self._cleanup(phone)
        return ConversationState.IDLE
