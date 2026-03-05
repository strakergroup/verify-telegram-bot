"""Tests for WhatsAppClient using respx to mock HTTP responses."""

import pytest
import respx
from httpx import Response

from src.whatsapp.client import WhatsAppAPIError, WhatsAppClient

PHONE_NUMBER_ID = "1234567890"
ACCESS_TOKEN = "test-token"
MESSAGES_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"


@pytest.fixture
def client() -> WhatsAppClient:
    return WhatsAppClient(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID)


class TestSendText:
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_text_success(self, client: WhatsAppClient) -> None:
        respx.post(MESSAGES_URL).mock(return_value=Response(200, json={"messages": [{"id": "msg_1"}]}))
        result = await client.send_text("+6421000000", "Hello")
        assert result["messages"][0]["id"] == "msg_1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_text_error(self, client: WhatsAppClient) -> None:
        respx.post(MESSAGES_URL).mock(
            return_value=Response(400, json={"error": {"message": "Invalid recipient"}})
        )
        with pytest.raises(WhatsAppAPIError) as exc_info:
            await client.send_text("+6421000000", "Hello")
        assert exc_info.value.status_code == 400
        assert "Invalid recipient" in exc_info.value.detail


class TestSendInteractiveList:
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_list_success(self, client: WhatsAppClient) -> None:
        respx.post(MESSAGES_URL).mock(return_value=Response(200, json={"messages": [{"id": "msg_2"}]}))
        result = await client.send_interactive_list(
            to="+6421000000",
            body="Pick a language",
            button_text="View",
            sections=[{"title": "Languages", "rows": [{"id": "en", "title": "English"}]}],
        )
        assert result["messages"][0]["id"] == "msg_2"


class TestSendInteractiveButtons:
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_buttons_success(self, client: WhatsAppClient) -> None:
        respx.post(MESSAGES_URL).mock(return_value=Response(200, json={"messages": [{"id": "msg_3"}]}))
        result = await client.send_interactive_buttons(
            to="+6421000000",
            body="Confirm?",
            buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
        )
        assert result["messages"][0]["id"] == "msg_3"


class TestDownloadMedia:
    @respx.mock
    @pytest.mark.asyncio
    async def test_download_media_success(self, client: WhatsAppClient) -> None:
        media_id = "media_abc"
        media_info_url = f"https://graph.facebook.com/v21.0/{media_id}"
        download_url = "https://lookaside.fbsbx.com/whatsapp_business/attachments/file.pdf"

        respx.get(media_info_url).mock(
            return_value=Response(200, json={"url": download_url, "mime_type": "application/pdf"})
        )
        respx.get(download_url).mock(return_value=Response(200, content=b"pdf-content"))

        content, mime = await client.download_media(media_id)
        assert content == b"pdf-content"
        assert mime == "application/pdf"

    @respx.mock
    @pytest.mark.asyncio
    async def test_download_media_no_url(self, client: WhatsAppClient) -> None:
        media_id = "media_bad"
        media_info_url = f"https://graph.facebook.com/v21.0/{media_id}"
        respx.get(media_info_url).mock(return_value=Response(200, json={"id": media_id}))

        with pytest.raises(WhatsAppAPIError) as exc_info:
            await client.download_media(media_id)
        assert "No download URL" in exc_info.value.detail


class TestMarkAsRead:
    @respx.mock
    @pytest.mark.asyncio
    async def test_mark_as_read_success(self, client: WhatsAppClient) -> None:
        respx.post(MESSAGES_URL).mock(return_value=Response(200, json={"success": True}))
        await client.mark_as_read("msg_123")
