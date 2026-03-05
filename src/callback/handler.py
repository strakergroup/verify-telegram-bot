"""Callback endpoint handler for Verify consumer notifications.

When the Verify consumer finishes processing a project, it POSTs to
/callback with the job_uuid and status. This handler looks up the
notification target (Telegram chat_id or WhatsApp phone) and sends
a notification to the appropriate platform.
"""

import logging

from pydantic import BaseModel
from telegram import Bot

from ..db.connection import get_notification_target
from ..whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)


class CallbackPayload(BaseModel):
    """Expected payload from the Verify consumer callback."""

    job_uuid: str
    status: str = ""
    message: str = ""


# Telegram templates (HTML)
TG_MESSAGES = {
    "COMPLETED": (
        "<b>Project Complete!</b>\n\n"
        "Your project <code>{job_uuid}</code> has finished processing.\n\n"
        "Use /download <code>{job_uuid}</code> to get your translated files."
    ),
    "UNSUCCESSFUL": (
        "<b>Project Failed</b>\n\n"
        "Your project <code>{job_uuid}</code> has failed.\n"
        "Reason: {message}\n\n"
        "Please try again with /translate."
    ),
    "PENDING_PAYMENT": (
        "<b>Project Pending Confirmation</b>\n\n"
        "Your project <code>{job_uuid}</code> requires confirmation.\n"
        "Message: {message}"
    ),
}

# WhatsApp templates (Markdown bold)
WA_MESSAGES = {
    "COMPLETED": (
        "*Project Complete!*\n\n"
        "Your project {job_uuid} has finished processing.\n\n"
        "Send *download {job_uuid}* to get your translated files."
    ),
    "UNSUCCESSFUL": (
        "*Project Failed*\n\n"
        "Your project {job_uuid} has failed.\n"
        "Reason: {message}\n\n"
        "Please try again with *translate*."
    ),
    "PENDING_PAYMENT": (
        "*Project Pending Confirmation*\n\n"
        "Your project {job_uuid} requires confirmation.\n"
        "Message: {message}"
    ),
}


async def handle_verify_callback(
    payload: CallbackPayload,
    bot: Bot,
    wa_client: WhatsAppClient | None = None,
) -> dict:
    """Process a Verify consumer callback and notify the user.

    Checks for both Telegram and WhatsApp notification targets
    and sends to whichever platform the project was created from.

    Args:
        payload: The callback data from the consumer.
        bot: The Telegram Bot instance for sending messages.
        wa_client: The WhatsApp client (optional, for WhatsApp notifications).

    Returns:
        A dict with processing status.
    """
    job_uuid = payload.job_uuid
    status = payload.status.upper()

    logger.info("Received callback for job %s with status %s", job_uuid, status)

    target = await get_notification_target(job_uuid)

    if not target.telegram_chat_id and not target.whatsapp_phone:
        logger.warning("No notification target found for job %s, skipping", job_uuid)
        return {"status": "ok", "notified": False, "reason": "no_target"}

    notified = False
    platforms: list[str] = []

    # Notify via Telegram
    if target.telegram_chat_id:
        template = TG_MESSAGES.get(status)
        if template:
            text = template.format(job_uuid=job_uuid, message=payload.message or "N/A")
            try:
                await bot.send_message(chat_id=target.telegram_chat_id, text=text, parse_mode="HTML")
                logger.info("Telegram notification sent to chat_id=%d for job %s", target.telegram_chat_id, job_uuid)
                notified = True
                platforms.append("telegram")
            except Exception:
                logger.exception("Failed to send Telegram notification for job %s", job_uuid)

    # Notify via WhatsApp
    if target.whatsapp_phone and wa_client:
        template = WA_MESSAGES.get(status)
        if template:
            text = template.format(job_uuid=job_uuid, message=payload.message or "N/A")
            try:
                await wa_client.send_text(target.whatsapp_phone, text)
                logger.info("WhatsApp notification sent to %s for job %s", target.whatsapp_phone, job_uuid)
                notified = True
                platforms.append("whatsapp")
            except Exception:
                logger.exception("Failed to send WhatsApp notification for job %s", job_uuid)

    if not notified:
        reason = "unhandled_status" if not TG_MESSAGES.get(status) else "send_failed"
        return {"status": "ok", "notified": False, "reason": reason}

    return {"status": "ok", "notified": True, "platforms": platforms}
