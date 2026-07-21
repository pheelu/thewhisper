"""Modelli ORM del dialogo: conversation, dialogue_message, dialogue_contact."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from whisper.dialogue.core.enums import (
    ContactType,
    ConversationOrigin,
    ConversationStatus,
    MessageKind,
)
from whisper.shared.infrastructure.db.base import (
    AppendOnlyMixin,
    Base,
    TimestampMixin,
    UUIDMixin,
)


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


class ConversationModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversation"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    initiator_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    origin: Mapped[ConversationOrigin] = mapped_column(
        _enum(ConversationOrigin, "conversation_origin"), nullable=False
    )
    status: Mapped[ConversationStatus] = mapped_column(
        _enum(ConversationStatus, "conversation_status"),
        nullable=False,
        default=ConversationStatus.active,
    )
    initiator_alias: Mapped[str] = mapped_column(Text, nullable=False)
    initiator_revealed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initiator_contact_consent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    recipient_contact_consent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    contact_exchanged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_reply_awarded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initiator_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recipient_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Una sola conversazione da missiva per coppia (initiator, recipient) per evento.
        Index(
            "uq_conversation_missive_pair",
            "event_id",
            "initiator_id",
            "recipient_id",
            unique=True,
            postgresql_where=text("origin = 'missive'"),
        ),
        Index("ix_conversation_initiator", "event_id", "initiator_id"),
        Index("ix_conversation_recipient", "event_id", "recipient_id"),
        CheckConstraint("initiator_id <> recipient_id", name="distinct_parties"),
    )


class DialogueMessageModel(UUIDMixin, AppendOnlyMixin, Base):
    __tablename__ = "dialogue_message"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[UUID | None] = mapped_column(ForeignKey("participant.id", ondelete="CASCADE"))
    kind: Mapped[MessageKind] = mapped_column(
        _enum(MessageKind, "message_kind"), nullable=False, default=MessageKind.text
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_dialogue_message_conversation", "conversation_id", "created_at"),
        CheckConstraint("kind = 'system' OR char_length(body) BETWEEN 1 AND 1000", name="body_len"),
    )


class DialogueContactModel(UUIDMixin, AppendOnlyMixin, Base):
    __tablename__ = "dialogue_contact"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    contact_type: Mapped[ContactType] = mapped_column(
        _enum(ContactType, "dialogue_contact_type"), nullable=False
    )
    contact_value_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    __table_args__ = (
        Index(
            "uq_dialogue_contact_owner",
            "conversation_id",
            "participant_id",
            "contact_type",
            unique=True,
        ),
        Index("ix_dialogue_contact_event", "event_id"),
    )
