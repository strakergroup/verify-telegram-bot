"""ECFMG certified translation workflow handler for Telegram.

Collects personal details, language pair, country, file, terms acceptance,
and optional notes. Submits to the Order API (file/save + /job) and returns
the quote with a payment link.
"""

import logging
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from ...config import Settings
from ...order.client import OrderAPIError, OrderClient
from ...order.models import ECFMG_TARGET_LANG_CODE, ECFMG_TARGET_LANG_LABEL
from ...session.store import SessionStore
from ..keyboards import (
    ECFMG_CONFIRM_NO,
    ECFMG_CONFIRM_YES,
    ECFMG_COUNTRY_PAGE_PREFIX,
    ECFMG_COUNTRY_PREFIX,
    ECFMG_LANG_PREFIX,
    ECFMG_NOTES_SKIP,
    ECFMG_TERMS_ACCEPT,
    ECFMG_TERMS_DECLINE,
    LANG_CANCEL,
    build_country_keyboard,
    build_ecfmg_confirm_keyboard,
    build_ecfmg_language_keyboard,
    build_ecfmg_notes_keyboard,
    build_terms_keyboard,
)
from ..states import ECFMGStates

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

CTX_SESSION = "ecfmg_session"
CTX_FIRSTNAME = "ecfmg_firstname"
CTX_LASTNAME = "ecfmg_lastname"
CTX_EMAIL = "ecfmg_email"
CTX_PHONE = "ecfmg_phone"
CTX_SOURCE_LANG = "ecfmg_source_lang"
CTX_SOURCE_LANG_LABEL = "ecfmg_source_lang_label"
CTX_COUNTRY = "ecfmg_country"
CTX_COUNTRY_LABEL = "ecfmg_country_label"
CTX_COUNTRY_PAGE = "ecfmg_country_page"
CTX_COUNTRY_SEARCH = "ecfmg_country_search"
CTX_FILE = "ecfmg_file"
CTX_TEMP_DIR = "ecfmg_temp_dir"
CTX_ACCEPT_TERMS = "ecfmg_accept_terms"
CTX_MARKETING = "ecfmg_marketing"
CTX_NOTES = "ecfmg_notes"

ALL_CTX_KEYS = (
    CTX_SESSION, CTX_FIRSTNAME, CTX_LASTNAME, CTX_EMAIL, CTX_PHONE,
    CTX_SOURCE_LANG, CTX_SOURCE_LANG_LABEL, CTX_COUNTRY, CTX_COUNTRY_LABEL,
    CTX_COUNTRY_PAGE, CTX_COUNTRY_SEARCH, CTX_FILE, CTX_TEMP_DIR,
    CTX_ACCEPT_TERMS, CTX_MARKETING, CTX_NOTES,
)


def _cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    temp_dir = context.user_data.get(CTX_TEMP_DIR)  # type: ignore[union-attr]
    if temp_dir and Path(temp_dir).exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    for key in ALL_CTX_KEYS:
        context.user_data.pop(key, None)  # type: ignore[union-attr]


def create_ecfmg_handlers(
    session_store: SessionStore,
    order_client: OrderClient,
    settings: Settings | None = None,
) -> dict:
    """Create ECFMG workflow handler functions with injected dependencies."""

    async def ecfmg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_message or not update.effective_user:
            return ConversationHandler.END

        temp_dir = tempfile.mkdtemp(prefix="verify_ecfmg_")
        context.user_data[CTX_SESSION] = str(uuid.uuid4()).upper()  # type: ignore[index]
        context.user_data[CTX_TEMP_DIR] = temp_dir  # type: ignore[index]

        await update.effective_message.reply_text(
            "<b>ECFMG Certified Translation</b>\n\n"
            "I'll guide you through the order process.\n"
            f"Target language is fixed to <b>{ECFMG_TARGET_LANG_LABEL}</b>.\n\n"
            "<b>Step 1/8: First Name</b>\n"
            "Please enter your first name:",
            parse_mode="HTML",
        )
        return ECFMGStates.AWAITING_FIRSTNAME

    async def receive_firstname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_message or not update.effective_message.text:
            return ECFMGStates.AWAITING_FIRSTNAME

        firstname = update.effective_message.text.strip()
        if not firstname or len(firstname) > 100:
            await update.effective_message.reply_text("Please enter a valid first name (1-100 characters).")
            return ECFMGStates.AWAITING_FIRSTNAME

        context.user_data[CTX_FIRSTNAME] = firstname  # type: ignore[index]
        await update.effective_message.reply_text(
            "<b>Step 2/8: Last Name</b>\n"
            "Please enter your last name:",
            parse_mode="HTML",
        )
        return ECFMGStates.AWAITING_LASTNAME

    async def receive_lastname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_message or not update.effective_message.text:
            return ECFMGStates.AWAITING_LASTNAME

        lastname = update.effective_message.text.strip()
        if not lastname or len(lastname) > 100:
            await update.effective_message.reply_text("Please enter a valid last name (1-100 characters).")
            return ECFMGStates.AWAITING_LASTNAME

        context.user_data[CTX_LASTNAME] = lastname  # type: ignore[index]
        await update.effective_message.reply_text(
            "<b>Step 3/8: Email Address</b>\n"
            "Please enter your email address:",
            parse_mode="HTML",
        )
        return ECFMGStates.AWAITING_EMAIL

    async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_message or not update.effective_message.text:
            return ECFMGStates.AWAITING_EMAIL

        email = update.effective_message.text.strip()
        if not EMAIL_PATTERN.match(email):
            await update.effective_message.reply_text(
                "That doesn't look like a valid email address. Please try again."
            )
            return ECFMGStates.AWAITING_EMAIL

        context.user_data[CTX_EMAIL] = email  # type: ignore[index]
        await update.effective_message.reply_text(
            "<b>Step 4/8: Phone Number</b>\n"
            "Please enter your phone number:",
            parse_mode="HTML",
        )
        return ECFMGStates.AWAITING_PHONE

    async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_message or not update.effective_message.text:
            return ECFMGStates.AWAITING_PHONE

        phone = update.effective_message.text.strip()
        if not phone or len(phone) < 5:
            await update.effective_message.reply_text("Please enter a valid phone number.")
            return ECFMGStates.AWAITING_PHONE

        context.user_data[CTX_PHONE] = phone  # type: ignore[index]

        try:
            languages = await order_client.get_ecfmg_languages()
        except Exception:
            logger.exception("Failed to fetch ECFMG languages")
            await update.effective_message.reply_text(
                "Failed to fetch language list. Please try again later."
            )
            _cleanup(context)
            return ConversationHandler.END

        if not languages:
            await update.effective_message.reply_text("No ECFMG languages available. Please try again later.")
            _cleanup(context)
            return ConversationHandler.END

        keyboard = build_ecfmg_language_keyboard(languages)
        await update.effective_message.reply_text(
            "<b>Step 5/8: Source Language</b>\n"
            "Select the language of your document:",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return ECFMGStates.AWAITING_SOURCE_LANG

    async def handle_source_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if not query or not query.data:
            return ECFMGStates.AWAITING_SOURCE_LANG

        await query.answer()

        if query.data == LANG_CANCEL:
            await query.edit_message_text("ECFMG order cancelled.")
            _cleanup(context)
            return ConversationHandler.END

        if query.data.startswith(ECFMG_LANG_PREFIX):
            lang_code = query.data[len(ECFMG_LANG_PREFIX):]
            languages = await order_client.get_ecfmg_languages()
            lang_obj = next((l for l in languages if l.code == lang_code), None)
            label = lang_obj.display_name if lang_obj else lang_code

            context.user_data[CTX_SOURCE_LANG] = lang_code  # type: ignore[index]
            context.user_data[CTX_SOURCE_LANG_LABEL] = label  # type: ignore[index]
            context.user_data[CTX_COUNTRY_PAGE] = 0  # type: ignore[index]
            context.user_data[CTX_COUNTRY_SEARCH] = ""  # type: ignore[index]

            try:
                countries = await order_client.get_countries()
            except Exception:
                logger.exception("Failed to fetch countries")
                await query.edit_message_text("Failed to fetch country list. Please try again later.")
                _cleanup(context)
                return ConversationHandler.END

            keyboard = build_country_keyboard(countries, page=0)
            await query.edit_message_text(
                f"Source language: <b>{label}</b>\n"
                f"Target language: <b>{ECFMG_TARGET_LANG_LABEL}</b>\n\n"
                "<b>Step 6/8: Country</b>\n"
                "Select your country, or type a name to search:",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return ECFMGStates.AWAITING_COUNTRY

        return ECFMGStates.AWAITING_SOURCE_LANG

    async def handle_country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if not query or not query.data:
            return ECFMGStates.AWAITING_COUNTRY

        await query.answer()
        data = query.data

        if data == LANG_CANCEL:
            await query.edit_message_text("ECFMG order cancelled.")
            _cleanup(context)
            return ConversationHandler.END

        if data.startswith(ECFMG_COUNTRY_PREFIX):
            country_id = data[len(ECFMG_COUNTRY_PREFIX):]
            countries = await order_client.get_countries()
            country_obj = next((c for c in countries if c.id_str == country_id), None)
            label = country_obj.display_name if country_obj else country_id

            context.user_data[CTX_COUNTRY] = country_id  # type: ignore[index]
            context.user_data[CTX_COUNTRY_LABEL] = label  # type: ignore[index]

            await query.edit_message_text(
                f"Country: <b>{label}</b>\n\n"
                "<b>Step 7/8: Upload Document</b>\n"
                "Send me the document you need translated (<b>PDF only</b>).\n"
                "Send /cancel to abort.",
                parse_mode="HTML",
            )
            return ECFMGStates.AWAITING_FILE

        if data.startswith(ECFMG_COUNTRY_PAGE_PREFIX):
            page = int(data[len(ECFMG_COUNTRY_PAGE_PREFIX):])
            context.user_data[CTX_COUNTRY_PAGE] = page  # type: ignore[index]
            search = context.user_data.get(CTX_COUNTRY_SEARCH, "")  # type: ignore[union-attr]
            countries = await order_client.get_countries()
            keyboard = build_country_keyboard(countries, page=page, search_query=search)
            try:
                await query.edit_message_text(
                    "<b>Step 6/8: Country</b>\n"
                    "Select your country, or type a name to search:",
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            except Exception:
                pass
            return ECFMGStates.AWAITING_COUNTRY

        return ECFMGStates.AWAITING_COUNTRY

    async def handle_country_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_message or not update.effective_message.text:
            return ECFMGStates.AWAITING_COUNTRY

        search = update.effective_message.text.strip()
        context.user_data[CTX_COUNTRY_SEARCH] = search  # type: ignore[index]
        context.user_data[CTX_COUNTRY_PAGE] = 0  # type: ignore[index]

        countries = await order_client.get_countries()
        keyboard = build_country_keyboard(countries, page=0, search_query=search)
        await update.effective_message.reply_text(
            f'<b>Step 6/8: Country</b>\nSearch: "{search}"\n'
            "Select your country:",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return ECFMGStates.AWAITING_COUNTRY

    async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_message:
            return ECFMGStates.AWAITING_FILE

        message = update.effective_message
        document = message.document

        if not document:
            await message.reply_text("Please send a PDF file as a document attachment.")
            return ECFMGStates.AWAITING_FILE

        file_name = document.file_name or ""
        if not file_name.lower().endswith(".pdf"):
            await message.reply_text(
                "Only PDF files are accepted for ECFMG orders. "
                "Please send a <b>.pdf</b> file.",
                parse_mode="HTML",
            )
            return ECFMGStates.AWAITING_FILE

        temp_dir = context.user_data.get(CTX_TEMP_DIR, "")  # type: ignore[union-attr]
        if not temp_dir:
            await message.reply_text("Session error. Please start over with /ecfmg.")
            _cleanup(context)
            return ConversationHandler.END

        file_name = document.file_name or f"file_{document.file_unique_id}"
        file_path = Path(temp_dir) / file_name

        status_msg = await message.reply_text(
            f"Downloading <code>{file_name}</code>...", parse_mode="HTML",
        )
        try:
            tg_file = await document.get_file()
            await tg_file.download_to_drive(str(file_path))
            context.user_data[CTX_FILE] = str(file_path)  # type: ignore[index]

            await status_msg.edit_text(
                f"Received <code>{file_name}</code>\n\n"
                "<b>Step 8/8: Terms & Conditions</b>\n\n"
                "By proceeding, you accept Straker's terms and conditions "
                "and agree to receive communications about Straker's products and services.\n\n"
                "Do you accept?",
                parse_mode="HTML",
                reply_markup=build_terms_keyboard(),
            )
            return ECFMGStates.AWAITING_TERMS
        except Exception:
            logger.exception("Failed to download file %s", file_name)
            await status_msg.edit_text(
                f"Failed to download <code>{file_name}</code>. Please try again.",
                parse_mode="HTML",
            )
            return ECFMGStates.AWAITING_FILE

    async def handle_terms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if not query or not query.data:
            return ECFMGStates.AWAITING_TERMS

        await query.answer()

        if query.data == ECFMG_TERMS_DECLINE:
            await query.edit_message_text(
                "You must accept the terms to proceed. Order cancelled."
            )
            _cleanup(context)
            return ConversationHandler.END

        if query.data == ECFMG_TERMS_ACCEPT:
            context.user_data[CTX_ACCEPT_TERMS] = True  # type: ignore[index]
            context.user_data[CTX_MARKETING] = True  # type: ignore[index]

            await query.edit_message_text(
                "Terms accepted.\n\n"
                "<b>Additional Notes</b> (optional)\n"
                "Enter any notes for the translator, or tap <b>Skip</b>.",
                parse_mode="HTML",
                reply_markup=build_ecfmg_notes_keyboard(),
            )
            return ECFMGStates.AWAITING_NOTES

        return ECFMGStates.AWAITING_TERMS

    async def handle_notes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if not query or not query.data:
            return ECFMGStates.AWAITING_NOTES

        await query.answer()

        if query.data == LANG_CANCEL:
            await query.edit_message_text("ECFMG order cancelled.")
            _cleanup(context)
            return ConversationHandler.END

        if query.data == ECFMG_NOTES_SKIP:
            context.user_data[CTX_NOTES] = ""  # type: ignore[index]
            return await _show_confirmation(query, context)

        return ECFMGStates.AWAITING_NOTES

    async def handle_notes_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_message or not update.effective_message.text:
            return ECFMGStates.AWAITING_NOTES

        notes = update.effective_message.text.strip()
        context.user_data[CTX_NOTES] = notes  # type: ignore[index]
        return await _show_confirmation_msg(update.effective_message, context)

    async def _show_confirmation(query, context: ContextTypes.DEFAULT_TYPE) -> int:
        ud = context.user_data  # type: ignore[union-attr]
        file_name = Path(ud.get(CTX_FILE, "")).name
        summary = (
            "<b>Order Summary</b>\n\n"
            f"<b>Name:</b> {ud.get(CTX_FIRSTNAME)} {ud.get(CTX_LASTNAME)}\n"
            f"<b>Email:</b> {ud.get(CTX_EMAIL)}\n"
            f"<b>Phone:</b> {ud.get(CTX_PHONE)}\n"
            f"<b>From:</b> {ud.get(CTX_SOURCE_LANG_LABEL)}\n"
            f"<b>To:</b> {ECFMG_TARGET_LANG_LABEL}\n"
            f"<b>Country:</b> {ud.get(CTX_COUNTRY_LABEL)}\n"
            f"<b>File:</b> {file_name}\n"
        )
        notes = ud.get(CTX_NOTES, "")
        if notes:
            summary += f"<b>Notes:</b> {notes}\n"
        summary += "\nPress <b>Order Now</b> to submit or <b>Cancel</b> to abort."

        await query.edit_message_text(
            summary,
            parse_mode="HTML",
            reply_markup=build_ecfmg_confirm_keyboard(),
        )
        return ECFMGStates.CONFIRM

    async def _show_confirmation_msg(message, context: ContextTypes.DEFAULT_TYPE) -> int:
        ud = context.user_data  # type: ignore[union-attr]
        file_name = Path(ud.get(CTX_FILE, "")).name
        summary = (
            "<b>Order Summary</b>\n\n"
            f"<b>Name:</b> {ud.get(CTX_FIRSTNAME)} {ud.get(CTX_LASTNAME)}\n"
            f"<b>Email:</b> {ud.get(CTX_EMAIL)}\n"
            f"<b>Phone:</b> {ud.get(CTX_PHONE)}\n"
            f"<b>From:</b> {ud.get(CTX_SOURCE_LANG_LABEL)}\n"
            f"<b>To:</b> {ECFMG_TARGET_LANG_LABEL}\n"
            f"<b>Country:</b> {ud.get(CTX_COUNTRY_LABEL)}\n"
            f"<b>File:</b> {file_name}\n"
        )
        notes = ud.get(CTX_NOTES, "")
        if notes:
            summary += f"<b>Notes:</b> {notes}\n"
        summary += "\nPress <b>Order Now</b> to submit or <b>Cancel</b> to abort."

        await message.reply_text(
            summary,
            parse_mode="HTML",
            reply_markup=build_ecfmg_confirm_keyboard(),
        )
        return ECFMGStates.CONFIRM

    async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        if not query or not query.data or not update.effective_user:
            return ConversationHandler.END

        await query.answer()

        if query.data == ECFMG_CONFIRM_NO:
            await query.edit_message_text("ECFMG order cancelled.")
            _cleanup(context)
            return ConversationHandler.END

        if query.data != ECFMG_CONFIRM_YES:
            return ECFMGStates.CONFIRM

        ud = context.user_data  # type: ignore[union-attr]
        file_path = Path(ud.get(CTX_FILE, ""))
        session_token = ud.get(CTX_SESSION, "")

        await query.edit_message_text("Submitting your order... Please wait.")

        try:
            await order_client.upload_file(
                file_path=file_path,
                session_token=session_token,
            )

            job_result = await order_client.create_job(
                firstname=ud.get(CTX_FIRSTNAME, ""),
                lastname=ud.get(CTX_LASTNAME, ""),
                email=ud.get(CTX_EMAIL, ""),
                phone=ud.get(CTX_PHONE, ""),
                source_lang=ud.get(CTX_SOURCE_LANG, ""),
                target_lang=ECFMG_TARGET_LANG_CODE,
                country=ud.get(CTX_COUNTRY, ""),
                session_token=session_token,
                notes=ud.get(CTX_NOTES, ""),
                accept_terms=ud.get(CTX_ACCEPT_TERMS, True),
                marketing_optin=ud.get(CTX_MARKETING, True),
            )

            email = ud.get(CTX_EMAIL, job_result.emailto or "")
            quote = job_result.quotes[0] if job_result.quotes else None
            msg_parts = [
                "<b>ECFMG Order Submitted!</b>\n",
                f"<b>Job ID:</b> TJ{job_result.jobid}",
                f"<b>From:</b> {job_result.sl}",
                f"<b>To:</b> {job_result.tl}",
                f"<b>E-mail:</b> {email}",
                f"<b>File:</b> {file_path.name}",
            ]

            if quote:
                msg_parts.extend([
                    "",
                    f"<b>Price:</b> {quote.price} ({job_result.currency})",
                    f"<b>Subtotal:</b> {job_result.cSymbl} {quote.subtotal}",
                ])
                if quote.tax_name and quote.tax != "0.00":
                    msg_parts.append(
                        f"<b>{quote.tax_name}:</b> {job_result.cSymbl} {quote.tax}"
                    )
                msg_parts.append(
                    f"<b>Total:</b> {job_result.cSymbl}{quote.total}"
                )
                if quote.paymentLink:
                    msg_parts.extend([
                        "",
                        f'<a href="{quote.paymentLink}">Pay Now</a>',
                    ])
            else:
                msg_parts.extend([
                    "",
                    "Your document is being processed. "
                    f"A quote and payment link will be sent to <b>{email}</b> shortly.",
                ])

            await query.edit_message_text(
                "\n".join(msg_parts),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(
                "ECFMG job %d created by user %d",
                job_result.jobid, update.effective_user.id,
            )
        except OrderAPIError as e:
            logger.error("ECFMG order failed: %s", e.detail)
            await query.edit_message_text(
                f"Order failed: {e.detail}\n\nPlease try again with /ecfmg."
            )
        except Exception:
            logger.exception("Unexpected error during ECFMG order")
            await query.edit_message_text(
                "An unexpected error occurred. Please try again later."
            )

        _cleanup(context)
        return ConversationHandler.END

    async def cancel_ecfmg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.effective_message:
            await update.effective_message.reply_text("ECFMG order cancelled.")
        _cleanup(context)
        return ConversationHandler.END

    return {
        "ecfmg_command": ecfmg_command,
        "receive_firstname": receive_firstname,
        "receive_lastname": receive_lastname,
        "receive_email": receive_email,
        "receive_phone": receive_phone,
        "handle_source_lang": handle_source_lang,
        "handle_country_callback": handle_country_callback,
        "handle_country_search": handle_country_search,
        "receive_file": receive_file,
        "handle_terms": handle_terms,
        "handle_notes_callback": handle_notes_callback,
        "handle_notes_text": handle_notes_text,
        "handle_confirm": handle_confirm,
        "cancel_ecfmg": cancel_ecfmg,
    }
