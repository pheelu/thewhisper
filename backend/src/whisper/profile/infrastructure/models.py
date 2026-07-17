"""Modello ORM del profilo: tabella `participant_profile` (1:1 con participant)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whisper.profile.core.enums import ProfileRevealStage
from whisper.shared.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


class ParticipantProfileModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "participant_profile"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    secret_text: Mapped[str | None] = mapped_column(Text)
    motto: Mapped[str | None] = mapped_column(Text)
    avatar_seed: Mapped[str] = mapped_column(Text, nullable=False)
    accent_color: Mapped[str | None] = mapped_column(Text)
    clues: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    reveal_stage: Mapped[ProfileRevealStage] = mapped_column(
        Enum(
            ProfileRevealStage,
            name="profile_reveal_stage",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ProfileRevealStage.concealed,
    )
    is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disclosed_publicly_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("uq_participant_profile_participant_id", "participant_id", unique=True),
        Index("ix_participant_profile_event_id", "event_id"),
        CheckConstraint(
            "accent_color IS NULL OR accent_color ~ '^#[0-9a-fA-F]{6}$'", name="accent_hex"
        ),
    )
