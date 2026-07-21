"""Schemi Pydantic del dialogo."""

from uuid import UUID

from pydantic import BaseModel, Field

from whisper.dialogue.core.enums import ContactType


class SendMissiveRequest(BaseModel):
    recipient_participant_id: UUID
    body: str = Field(min_length=1, max_length=1000)


class SendMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class ContactRequest(BaseModel):
    contact_type: ContactType = ContactType.instagram
    contact_value: str = Field(min_length=1, max_length=120)
