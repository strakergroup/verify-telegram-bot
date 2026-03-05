"""Pydantic models for WhatsApp Cloud API webhook payloads."""

from pydantic import BaseModel, Field


class WebhookProfile(BaseModel):
    name: str = ""


class WebhookContact(BaseModel):
    profile: WebhookProfile = Field(default_factory=WebhookProfile)
    wa_id: str = ""


class TextPayload(BaseModel):
    body: str = ""


class DocumentPayload(BaseModel):
    id: str = ""
    mime_type: str = ""
    sha256: str = ""
    filename: str = ""


class ImagePayload(BaseModel):
    id: str = ""
    mime_type: str = ""
    sha256: str = ""


class InteractivePayload(BaseModel):
    type: str = ""


class ListReplyPayload(BaseModel):
    id: str = ""
    title: str = ""
    description: str = ""


class ButtonReplyPayload(BaseModel):
    id: str = ""
    title: str = ""


class InteractiveResponse(BaseModel):
    type: str = ""
    list_reply: ListReplyPayload | None = None
    button_reply: ButtonReplyPayload | None = None


class WebhookMessage(BaseModel):
    """Represents a single incoming message from the webhook payload."""

    from_: str = Field(default="", alias="from")
    id: str = ""
    timestamp: str = ""
    type: str = ""
    text: TextPayload | None = None
    document: DocumentPayload | None = None
    image: ImagePayload | None = None
    interactive: InteractiveResponse | None = None

    model_config = {"populate_by_name": True}


class StatusPayload(BaseModel):
    id: str = ""
    status: str = ""
    timestamp: str = ""
    recipient_id: str = ""


class WebhookMetadata(BaseModel):
    display_phone_number: str = ""
    phone_number_id: str = ""


class WebhookValue(BaseModel):
    messaging_product: str = ""
    metadata: WebhookMetadata = Field(default_factory=WebhookMetadata)
    contacts: list[WebhookContact] = []
    messages: list[WebhookMessage] = []
    statuses: list[StatusPayload] = []


class WebhookChange(BaseModel):
    value: WebhookValue = Field(default_factory=WebhookValue)
    field: str = ""


class WebhookEntry(BaseModel):
    id: str = ""
    changes: list[WebhookChange] = []


class WebhookPayload(BaseModel):
    """Top-level webhook payload from Meta."""

    object: str = ""
    entry: list[WebhookEntry] = []

    def extract_messages(self) -> list[tuple[WebhookMessage, WebhookContact | None]]:
        """Extract all messages from the webhook payload with their contact info."""
        results: list[tuple[WebhookMessage, WebhookContact | None]] = []
        for entry in self.entry:
            for change in entry.changes:
                if change.field != "messages":
                    continue
                contacts = change.value.contacts
                contact_map = {c.wa_id: c for c in contacts}
                for message in change.value.messages:
                    contact = contact_map.get(message.from_)
                    results.append((message, contact))
        return results
