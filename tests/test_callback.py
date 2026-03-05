"""Tests for the callback handler module (multi-platform)."""

from unittest.mock import AsyncMock, patch

import pytest

from src.callback.handler import CallbackPayload, handle_verify_callback
from src.db.connection import NotificationTarget


class TestCallbackPayload:
    def test_valid_payload(self) -> None:
        payload = CallbackPayload(job_uuid="abc-123", status="COMPLETED", message="done")
        assert payload.job_uuid == "abc-123"
        assert payload.status == "COMPLETED"

    def test_defaults(self) -> None:
        payload = CallbackPayload(job_uuid="abc-123")
        assert payload.status == ""
        assert payload.message == ""


class TestHandleVerifyCallbackTelegram:
    @pytest.mark.asyncio
    async def test_no_target_found(self) -> None:
        mock_bot = AsyncMock()
        payload = CallbackPayload(job_uuid="unknown-job", status="COMPLETED")

        with patch(
            "src.callback.handler.get_notification_target",
            new_callable=AsyncMock,
            return_value=NotificationTarget(),
        ):
            result = await handle_verify_callback(payload, mock_bot)

        assert result["notified"] is False
        assert result["reason"] == "no_target"
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_telegram_completed_notification(self) -> None:
        mock_bot = AsyncMock()
        payload = CallbackPayload(job_uuid="proj-123", status="COMPLETED")

        with patch(
            "src.callback.handler.get_notification_target",
            new_callable=AsyncMock,
            return_value=NotificationTarget(telegram_chat_id=42),
        ):
            result = await handle_verify_callback(payload, mock_bot)

        assert result["notified"] is True
        assert "telegram" in result["platforms"]
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 42
        assert "proj-123" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_telegram_unsuccessful_notification(self) -> None:
        mock_bot = AsyncMock()
        payload = CallbackPayload(job_uuid="proj-456", status="UNSUCCESSFUL", message="bad file")

        with patch(
            "src.callback.handler.get_notification_target",
            new_callable=AsyncMock,
            return_value=NotificationTarget(telegram_chat_id=99),
        ):
            result = await handle_verify_callback(payload, mock_bot)

        assert result["notified"] is True
        call_kwargs = mock_bot.send_message.call_args[1]
        assert "Failed" in call_kwargs["text"]
        assert "bad file" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_unhandled_status(self) -> None:
        mock_bot = AsyncMock()
        payload = CallbackPayload(job_uuid="proj-xxx", status="UNKNOWN_STATUS")

        with patch(
            "src.callback.handler.get_notification_target",
            new_callable=AsyncMock,
            return_value=NotificationTarget(telegram_chat_id=42),
        ):
            result = await handle_verify_callback(payload, mock_bot)

        assert result["notified"] is False
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_telegram_send_failure(self) -> None:
        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = Exception("Telegram API down")
        payload = CallbackPayload(job_uuid="proj-err", status="COMPLETED")

        with patch(
            "src.callback.handler.get_notification_target",
            new_callable=AsyncMock,
            return_value=NotificationTarget(telegram_chat_id=42),
        ):
            result = await handle_verify_callback(payload, mock_bot)

        assert result["notified"] is False


class TestHandleVerifyCallbackWhatsApp:
    @pytest.mark.asyncio
    async def test_whatsapp_completed_notification(self) -> None:
        mock_bot = AsyncMock()
        mock_wa = AsyncMock()
        payload = CallbackPayload(job_uuid="proj-wa1", status="COMPLETED")

        with patch(
            "src.callback.handler.get_notification_target",
            new_callable=AsyncMock,
            return_value=NotificationTarget(whatsapp_phone="+6421000000"),
        ):
            result = await handle_verify_callback(payload, mock_bot, mock_wa)

        assert result["notified"] is True
        assert "whatsapp" in result["platforms"]
        mock_wa.send_text.assert_called_once()
        call_args = mock_wa.send_text.call_args[0]
        assert call_args[0] == "+6421000000"
        assert "proj-wa1" in call_args[1]
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_whatsapp_without_client(self) -> None:
        """WhatsApp target exists but no wa_client provided -- should skip."""
        mock_bot = AsyncMock()
        payload = CallbackPayload(job_uuid="proj-wa2", status="COMPLETED")

        with patch(
            "src.callback.handler.get_notification_target",
            new_callable=AsyncMock,
            return_value=NotificationTarget(whatsapp_phone="+6421000000"),
        ):
            result = await handle_verify_callback(payload, mock_bot, wa_client=None)

        assert result["notified"] is False

    @pytest.mark.asyncio
    async def test_both_platforms_notified(self) -> None:
        mock_bot = AsyncMock()
        mock_wa = AsyncMock()
        payload = CallbackPayload(job_uuid="proj-both", status="COMPLETED")

        with patch(
            "src.callback.handler.get_notification_target",
            new_callable=AsyncMock,
            return_value=NotificationTarget(telegram_chat_id=42, whatsapp_phone="+123"),
        ):
            result = await handle_verify_callback(payload, mock_bot, mock_wa)

        assert result["notified"] is True
        assert "telegram" in result["platforms"]
        assert "whatsapp" in result["platforms"]
        mock_bot.send_message.assert_called_once()
        mock_wa.send_text.assert_called_once()
