"""FastAPI application that hosts both the Telegram bot and WhatsApp bot.

Runs the python-telegram-bot Application inside a FastAPI server using the
custom webhook integration pattern. Exposes:
    POST /telegram-webhook     -- Telegram update handler
    GET  /whatsapp-webhook     -- Meta verification challenge
    POST /whatsapp-webhook     -- WhatsApp message handler
    POST /callback             -- Verify consumer callback (shared)
    GET  /health               -- Health check
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Response
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .bot.handlers.auth import create_auth_handlers
from .bot.handlers.balance import create_balance_handler
from .bot.handlers.download import create_download_handler
from .bot.handlers.ecfmg import create_ecfmg_handlers
from .bot.handlers.projects import create_project_handlers
from .bot.handlers.start import help_command, start_command
from .bot.handlers.translate import create_translate_handlers
from .bot.states import AuthStates, ECFMGStates, TranslateStates
from .callback.handler import CallbackPayload, handle_verify_callback
from .config import get_settings, setup_logging
from .db.connection import init_engine
from .order.client import OrderClient
from .session.store import SessionStore
from .verify.client import VerifyClient
from .whatsapp.client import WhatsAppClient
from .whatsapp.models import WebhookPayload
from .whatsapp.signature import validate_signature
from .whatsapp_bot.router import MessageRouter
from .whatsapp_bot.session_store import WhatsAppSessionStore

logger = logging.getLogger(__name__)


def _build_ptb_application(settings, session_store, verify_client, order_client):
    """Build and register all handlers on the python-telegram-bot Application."""
    auth_handlers = create_auth_handlers(session_store, verify_client)
    translate_handlers = create_translate_handlers(
        session_store, verify_client, settings,
    )
    ecfmg_handlers = create_ecfmg_handlers(session_store, order_client, settings)
    project_handlers = create_project_handlers(session_store, verify_client)
    balance_handlers = create_balance_handler(session_store, verify_client)
    download_handlers = create_download_handler(session_store, verify_client)

    ptb_app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token.get_secret_value())
        .updater(None)
        .build()
    )

    # Standalone command handlers
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(CommandHandler("help", help_command))
    ptb_app.add_handler(CommandHandler("logout", auth_handlers["logout_command"]))
    ptb_app.add_handler(CommandHandler("status", auth_handlers["status_command"]))
    ptb_app.add_handler(CommandHandler("projects", project_handlers["projects_command"]))
    ptb_app.add_handler(CommandHandler("project", project_handlers["project_detail_command"]))
    ptb_app.add_handler(CommandHandler("balance", balance_handlers["balance_command"]))
    ptb_app.add_handler(CommandHandler("download", download_handlers["download_command"]))

    # Login conversation handler
    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", auth_handlers["login_command"])],
        states={
            AuthStates.AWAITING_API_KEY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    auth_handlers["receive_api_key"],
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", auth_handlers["cancel_login"])],
    )
    ptb_app.add_handler(login_conv)

    # Translation conversation handler
    translate_conv = ConversationHandler(
        entry_points=[CommandHandler("translate", translate_handlers["translate_command"])],
        states={
            TranslateStates.AWAITING_FILE: [
                CommandHandler("done", translate_handlers["done_uploading"]),
                MessageHandler(filters.Document.ALL, translate_handlers["receive_file"]),
            ],
            TranslateStates.AWAITING_LANGUAGES: [
                CallbackQueryHandler(translate_handlers["handle_language_callback"]),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    translate_handlers["handle_language_search"],
                ),
            ],
            TranslateStates.AWAITING_TITLE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    translate_handlers["receive_title"],
                ),
            ],
            TranslateStates.CONFIRM: [
                CallbackQueryHandler(translate_handlers["handle_confirm_callback"]),
            ],
        },
        fallbacks=[CommandHandler("cancel", translate_handlers["cancel_translate"])],
        per_message=False,
    )
    ptb_app.add_handler(translate_conv)

    # ECFMG certified translation conversation handler
    ecfmg_conv = ConversationHandler(
        entry_points=[CommandHandler("ecfmg", ecfmg_handlers["ecfmg_command"])],
        states={
            ECFMGStates.AWAITING_FIRSTNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ecfmg_handlers["receive_firstname"]),
            ],
            ECFMGStates.AWAITING_LASTNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ecfmg_handlers["receive_lastname"]),
            ],
            ECFMGStates.AWAITING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ecfmg_handlers["receive_email"]),
            ],
            ECFMGStates.AWAITING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ecfmg_handlers["receive_phone"]),
            ],
            ECFMGStates.AWAITING_SOURCE_LANG: [
                CallbackQueryHandler(ecfmg_handlers["handle_source_lang"]),
            ],
            ECFMGStates.AWAITING_COUNTRY: [
                CallbackQueryHandler(ecfmg_handlers["handle_country_callback"]),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ecfmg_handlers["handle_country_search"]),
            ],
            ECFMGStates.AWAITING_FILE: [
                MessageHandler(filters.Document.ALL, ecfmg_handlers["receive_file"]),
            ],
            ECFMGStates.AWAITING_TERMS: [
                CallbackQueryHandler(ecfmg_handlers["handle_terms"]),
            ],
            ECFMGStates.AWAITING_NOTES: [
                CallbackQueryHandler(ecfmg_handlers["handle_notes_callback"]),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ecfmg_handlers["handle_notes_text"]),
            ],
            ECFMGStates.CONFIRM: [
                CallbackQueryHandler(ecfmg_handlers["handle_confirm"]),
            ],
        },
        fallbacks=[CommandHandler("cancel", ecfmg_handlers["cancel_ecfmg"])],
        per_message=False,
    )
    ptb_app.add_handler(ecfmg_conv)

    return ptb_app


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle for the FastAPI application."""
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info(
        "Starting Verify Bot (env=%s, port=%d, whatsapp=%s)",
        settings.environment.value,
        settings.port,
        "enabled" if settings.whatsapp_enabled else "disabled",
    )

    # Shared dependencies
    tg_session_store = SessionStore()
    verify_client = VerifyClient(settings.verify_api_url)
    order_client = OrderClient(settings.order_base_url)

    # Initialise verify DB engine (optional -- degrades gracefully)
    if settings.db_configured:
        init_engine(
            host=settings.verify_db_host,
            port=settings.verify_db_port,
            user=settings.verify_db_user,
            password=settings.verify_db_password.get_secret_value(),
            db_name=settings.verify_db_name,
        )
        logger.info("Verify DB connection configured")
    else:
        logger.warning("Verify DB not configured -- callback notifications will be disabled")

    # Build Telegram PTB application
    ptb_app = _build_ptb_application(settings, tg_session_store, verify_client, order_client)
    _app.state.ptb_app = ptb_app
    _app.state.settings = settings

    # Initialise PTB
    await ptb_app.initialize()
    await ptb_app.start()

    # Set the Telegram webhook
    if settings.webhook_base_url:
        webhook_url = f"{settings.webhook_base_url}/telegram-webhook"
        await ptb_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret or None,
            drop_pending_updates=True,
        )
        logger.info("Telegram webhook set to %s", webhook_url)
    else:
        logger.warning("WEBHOOK_BASE_URL not set -- Telegram webhook not registered")

    # Initialise WhatsApp (optional)
    wa_client: WhatsAppClient | None = None
    wa_router: MessageRouter | None = None
    if settings.whatsapp_enabled:
        wa_client = WhatsAppClient(
            access_token=settings.whatsapp_access_token.get_secret_value(),
            phone_number_id=settings.whatsapp_phone_number_id,
        )
        wa_session_store = WhatsAppSessionStore()
        wa_router = MessageRouter(
            wa_client, wa_session_store, verify_client, settings,
            order_client=order_client,
        )
        logger.info("WhatsApp bot initialised (phone_id=%s)", settings.whatsapp_phone_number_id)
    else:
        logger.info("WhatsApp not configured -- WhatsApp endpoints will return 503")

    _app.state.wa_client = wa_client
    _app.state.wa_router = wa_router

    yield

    # Shutdown
    await ptb_app.stop()
    await ptb_app.shutdown()
    logger.info("Bot shut down cleanly")


app = FastAPI(title="Verify Bot", lifespan=lifespan)


# ── Telegram routes ──────────────────────────────────────────────────────────


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request) -> Response:
    """Receive updates from Telegram."""
    ptb_app = request.app.state.ptb_app
    settings = request.app.state.settings

    if settings.webhook_secret:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != settings.webhook_secret:
            return Response(status_code=403, content="Forbidden")

    body = await request.json()
    update = Update.de_json(body, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)


# ── WhatsApp routes ──────────────────────────────────────────────────────────


@app.get("/whatsapp-webhook")
async def whatsapp_verify(
    request: Request,
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> Response:
    """Handle Meta webhook verification challenge."""
    settings = request.app.state.settings

    if not settings.whatsapp_enabled:
        raise HTTPException(status_code=503, detail="WhatsApp not configured")

    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("WhatsApp webhook verification successful")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("WhatsApp webhook verification failed: mode=%s", hub_mode)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/whatsapp-webhook")
async def whatsapp_webhook(request: Request) -> dict:
    """Handle incoming WhatsApp webhook events from Meta."""
    settings = request.app.state.settings
    wa_router: MessageRouter | None = request.app.state.wa_router

    if not settings.whatsapp_enabled or not wa_router:
        raise HTTPException(status_code=503, detail="WhatsApp not configured")

    body = await request.body()

    # Validate signature (skip in local env when app_secret is placeholder)
    app_secret = settings.whatsapp_app_secret.get_secret_value()
    if app_secret and app_secret != "placeholder":
        signature = request.headers.get("X-Hub-Signature-256")
        if not validate_signature(body, signature, app_secret):
            client_host = request.client.host if request.client else "unknown"
            logger.warning("Invalid WhatsApp webhook signature from %s", client_host)
            raise HTTPException(status_code=403, detail="Invalid signature")
    else:
        logger.debug("Skipping WhatsApp signature validation (app_secret not configured)")

    try:
        payload = WebhookPayload.model_validate_json(body)
    except Exception:
        logger.exception("Failed to parse WhatsApp webhook payload")
        raise HTTPException(status_code=400, detail="Invalid payload")

    messages = payload.extract_messages()
    for message, _contact in messages:
        try:
            await wa_router.route(message)
        except Exception:
            logger.exception("Error processing WhatsApp message %s from %s", message.id, message.from_)

    return {"status": "ok"}


# ── Shared routes ────────────────────────────────────────────────────────────


@app.post("/callback")
async def verify_callback(request: Request) -> dict:
    """Receive callbacks from the Verify consumer when a project completes."""
    ptb_app = request.app.state.ptb_app
    wa_client: WhatsAppClient | None = request.app.state.wa_client
    body = await request.json()

    payload = CallbackPayload.model_validate(body)
    result = await handle_verify_callback(payload, ptb_app.bot, wa_client)
    return result


@app.get("/health")
async def health_check(request: Request) -> dict:
    """Health check with feature status."""
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": "verify-bot",
        "telegram": True,
        "whatsapp": settings.whatsapp_enabled,
    }


def main() -> None:
    """Application entry point."""
    settings = get_settings()
    setup_logging(settings.log_level)
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
