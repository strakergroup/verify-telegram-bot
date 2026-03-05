"""Async client for the WhatsApp Cloud API (Meta Graph API v21.0)."""

import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class WhatsAppAPIError(Exception):
    """Raised when the WhatsApp Cloud API returns an error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"WhatsApp API error {status_code}: {detail}")


class WhatsAppClient:
    """Async client wrapping WhatsApp Cloud API message and media endpoints."""

    def __init__(self, access_token: str, phone_number_id: str) -> None:
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._messages_url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
        self._media_url = f"{GRAPH_API_BASE}/{phone_number_id}/media"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _check_response(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                body = response.json()
                error = body.get("error", {})
                detail = error.get("message", response.text)
            except Exception:
                detail = response.text
            raise WhatsAppAPIError(response.status_code, str(detail))

    async def send_text(self, to: str, body: str) -> dict:
        """Send a plain text message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._messages_url,
                headers=self._headers(),
                json=payload,
            )
            self._check_response(response)
            return response.json()

    async def send_interactive_list(
        self,
        to: str,
        body: str,
        button_text: str,
        sections: list[dict],
        header: str | None = None,
        footer: str | None = None,
    ) -> dict:
        """Send an interactive list message (max 10 items per section)."""
        action: dict = {"button": button_text, "sections": sections}
        interactive: dict = {
            "type": "list",
            "body": {"text": body},
            "action": action,
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._messages_url,
                headers=self._headers(),
                json=payload,
            )
            self._check_response(response)
            return response.json()

    async def send_interactive_buttons(
        self,
        to: str,
        body: str,
        buttons: list[dict],
        header: str | None = None,
        footer: str | None = None,
    ) -> dict:
        """Send an interactive reply-button message (max 3 buttons)."""
        formatted_buttons = [
            {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
            for b in buttons
        ]
        interactive: dict = {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": formatted_buttons},
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._messages_url,
                headers=self._headers(),
                json=payload,
            )
            self._check_response(response)
            return response.json()

    async def send_document(
        self,
        to: str,
        document_url: str | None = None,
        media_id: str | None = None,
        filename: str = "document",
        caption: str | None = None,
    ) -> dict:
        """Send a document message via URL or media_id."""
        doc: dict = {"filename": filename}
        if media_id:
            doc["id"] = media_id
        elif document_url:
            doc["link"] = document_url
        else:
            raise ValueError("Either document_url or media_id must be provided")

        if caption:
            doc["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": doc,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self._messages_url,
                headers=self._headers(),
                json=payload,
            )
            self._check_response(response)
            return response.json()

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """Download media by ID (two-step: get URL, then download)."""
        media_info_url = f"{GRAPH_API_BASE}/{media_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                media_info_url,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            self._check_response(response)
            info = response.json()

        download_url = info.get("url", "")
        mime_type = info.get("mime_type", "application/octet-stream")

        if not download_url:
            raise WhatsAppAPIError(404, "No download URL in media info response")

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(
                download_url,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            self._check_response(response)
            return response.content, mime_type

    async def upload_media(self, file_path: Path, mime_type: str) -> str:
        """Upload a file to WhatsApp and return the media_id."""
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                self._media_url,
                headers=headers,
                data={"messaging_product": "whatsapp", "type": mime_type},
                files={"file": (file_path.name, file_path.read_bytes(), mime_type)},
            )
            self._check_response(response)
            result = response.json()
            media_id: str = result.get("id", "")
            logger.info("Uploaded media %s as %s", file_path.name, media_id)
            return media_id

    async def mark_as_read(self, message_id: str) -> None:
        """Mark an incoming message as read."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self._messages_url,
                headers=self._headers(),
                json=payload,
            )
            self._check_response(response)
