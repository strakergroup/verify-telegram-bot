"""Tests for the DB connection module (store_chat_id / get_notification_target)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.db.connection import get_chat_id, get_notification_target, store_chat_id


class TestStoreChatId:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_engine(self) -> None:
        with patch("src.db.connection._engine", None):
            result = await store_chat_id("job-123", chat_id=42)
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_job_not_found(self) -> None:
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = None

        with patch("src.db.connection._engine", mock_engine):
            result = await store_chat_id("nonexistent-job", chat_id=42)
            assert result is False

    @pytest.mark.asyncio
    async def test_stores_telegram_chat_id_with_existing_extra_info(self) -> None:
        existing_extra = json.dumps({"mt_service": "google"})

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = (existing_extra,)

        with patch("src.db.connection._engine", mock_engine):
            result = await store_chat_id("job-123", chat_id=99999)
            assert result is True

        update_call = mock_conn.execute.call_args_list[1]
        params = update_call[0][1]
        written_extra = json.loads(params["extra"])
        assert written_extra["telegram_chat_id"] == 99999
        assert written_extra["mt_service"] == "google"

    @pytest.mark.asyncio
    async def test_stores_whatsapp_phone(self) -> None:
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = (None,)

        with patch("src.db.connection._engine", mock_engine):
            result = await store_chat_id("job-456", whatsapp_phone="+6421000000")
            assert result is True

        update_call = mock_conn.execute.call_args_list[1]
        params = update_call[0][1]
        written_extra = json.loads(params["extra"])
        assert written_extra["whatsapp_phone"] == "+6421000000"
        assert "telegram_chat_id" not in written_extra

    @pytest.mark.asyncio
    async def test_stores_both_identifiers(self) -> None:
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = ("{}",)

        with patch("src.db.connection._engine", mock_engine):
            result = await store_chat_id("job-789", chat_id=42, whatsapp_phone="+123")
            assert result is True

        update_call = mock_conn.execute.call_args_list[1]
        params = update_call[0][1]
        written_extra = json.loads(params["extra"])
        assert written_extra["telegram_chat_id"] == 42
        assert written_extra["whatsapp_phone"] == "+123"


class TestGetNotificationTarget:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_engine(self) -> None:
        with patch("src.db.connection._engine", None):
            target = await get_notification_target("job-123")
            assert target.telegram_chat_id is None
            assert target.whatsapp_phone is None

    @pytest.mark.asyncio
    async def test_returns_telegram_chat_id(self) -> None:
        extra = json.dumps({"telegram_chat_id": 42})

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = (extra,)

        with patch("src.db.connection._engine", mock_engine):
            target = await get_notification_target("job-123")
            assert target.telegram_chat_id == 42
            assert target.whatsapp_phone is None

    @pytest.mark.asyncio
    async def test_returns_whatsapp_phone(self) -> None:
        extra = json.dumps({"whatsapp_phone": "+6421000000"})

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = (extra,)

        with patch("src.db.connection._engine", mock_engine):
            target = await get_notification_target("job-123")
            assert target.telegram_chat_id is None
            assert target.whatsapp_phone == "+6421000000"

    @pytest.mark.asyncio
    async def test_returns_both(self) -> None:
        extra = json.dumps({"telegram_chat_id": 99, "whatsapp_phone": "+123"})

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = (extra,)

        with patch("src.db.connection._engine", mock_engine):
            target = await get_notification_target("job-123")
            assert target.telegram_chat_id == 99
            assert target.whatsapp_phone == "+123"


class TestGetChatId:
    @pytest.mark.asyncio
    async def test_convenience_wrapper(self) -> None:
        extra = json.dumps({"telegram_chat_id": 42, "whatsapp_phone": "+123"})

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = (extra,)

        with patch("src.db.connection._engine", mock_engine):
            result = await get_chat_id("job-123")
            assert result == 42

    @pytest.mark.asyncio
    async def test_returns_none_when_no_engine(self) -> None:
        with patch("src.db.connection._engine", None):
            result = await get_chat_id("job-123")
            assert result is None
