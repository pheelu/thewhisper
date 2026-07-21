"""Entità di dominio del dialogo."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from whisper.dialogue.core.enums import (
    ContactType,
    ConversationOrigin,
    ConversationStatus,
    MessageKind,
)
from whisper.shared.core.entity import BaseEntity, TimestampedEntity


@dataclass(kw_only=True)
class Conversation(TimestampedEntity):
    event_id: UUID
    initiator_id: UUID
    recipient_id: UUID
    origin: ConversationOrigin
    status: ConversationStatus
    # Alias con cui il mittente resta mascherato finché non si rivela.
    initiator_alias: str
    initiator_revealed: bool
    revealed_at: datetime | None
    initiator_contact_consent: bool
    recipient_contact_consent: bool
    contact_exchanged_at: datetime | None
    first_reply_awarded: bool
    last_message_at: datetime | None
    initiator_last_read_at: datetime | None
    recipient_last_read_at: datetime | None

    def side_of(self, participant_id: UUID) -> str | None:
        if participant_id == self.initiator_id:
            return "initiator"
        if participant_id == self.recipient_id:
            return "recipient"
        return None

    def counterpart_of(self, participant_id: UUID) -> UUID:
        return self.recipient_id if participant_id == self.initiator_id else self.initiator_id

    @property
    def contact_exchange_ready(self) -> bool:
        """Lo scambio contatti richiede doppio consenso E il mittente rivelato."""
        return (
            self.initiator_contact_consent
            and self.recipient_contact_consent
            and self.initiator_revealed
            and self.contact_exchanged_at is None
        )


@dataclass(kw_only=True)
class Message(BaseEntity):
    event_id: UUID
    conversation_id: UUID
    sender_id: UUID | None  # None per i messaggi di sistema
    kind: MessageKind
    body: str
    created_at: datetime


@dataclass(kw_only=True)
class Contact(BaseEntity):
    event_id: UUID
    conversation_id: UUID
    participant_id: UUID
    contact_type: ContactType
    contact_value: str  # in chiaro solo in memoria; cifrato a riposo
    created_at: datetime
