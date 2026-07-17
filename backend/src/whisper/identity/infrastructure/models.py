"""Modelli ORM del dominio identity: tabelle `event` e `participant`."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whisper.shared.core.enums import EventStatus, ParticipantNobleTitle, ParticipantRole
from whisper.shared.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


class EventModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "event"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    venue_name: Mapped[str | None] = mapped_column(Text)
    join_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        _enum(EventStatus, "event_status"), nullable=False, default=EventStatus.draft
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="Europe/Rome")
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    host_secret_hash: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    __table_args__ = (
        Index("uq_event_join_code", func.lower(join_code), unique=True),
        Index("ix_event_status", "status"),
        CheckConstraint("ends_at > starts_at", name="window"),
    )


class ParticipantModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "participant"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    pseudonym: Mapped[str] = mapped_column(Text, nullable=False)
    noble_title: Mapped[ParticipantNobleTitle | None] = mapped_column(
        _enum(ParticipantNobleTitle, "participant_noble_title")
    )
    role: Mapped[ParticipantRole] = mapped_column(
        _enum(ParticipantRole, "participant_role"), nullable=False, default=ParticipantRole.guest
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_photographable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_token_id: Mapped[UUID] = mapped_column(nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("uq_participant_event_pseudonym", "event_id", func.lower(pseudonym), unique=True),
        Index("ix_participant_event_id", "event_id"),
        CheckConstraint(
            "role <> 'host' OR is_photographable = false", name="host_not_photographable"
        ),
    )
