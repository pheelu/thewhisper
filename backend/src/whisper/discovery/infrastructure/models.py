"""Modelli ORM della scoperta: commenti, guess, stato di scoperta."""

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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from whisper.discovery.core.enums import CommentStatus, DiscoveryRevealState
from whisper.shared.infrastructure.db.base import (
    AppendOnlyMixin,
    Base,
    TimestampMixin,
    UUIDMixin,
)


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


class WhisperCommentModel(UUIDMixin, AppendOnlyMixin, Base):
    __tablename__ = "whisper_comment"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    photo_id: Mapped[UUID] = mapped_column(
        ForeignKey("photo.id", ondelete="CASCADE"), nullable=False
    )
    author_participant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CommentStatus] = mapped_column(
        _enum(CommentStatus, "comment_status"), nullable=False, default=CommentStatus.visible
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_whisper_comment_event_photo_created", "event_id", "photo_id", "created_at"),
        Index("ix_whisper_comment_author", "author_participant_id"),
        CheckConstraint("char_length(btrim(body)) BETWEEN 1 AND 500", name="body_len"),
    )


class WhisperGuessModel(UUIDMixin, AppendOnlyMixin, Base):
    __tablename__ = "whisper_guess"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    photo_id: Mapped[UUID] = mapped_column(
        ForeignKey("photo.id", ondelete="CASCADE"), nullable=False
    )
    guesser_participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    guessed_subject_participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guess_rank: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index(
            "uq_whisper_guess_photo_guesser_candidate",
            "photo_id",
            "guesser_participant_id",
            "guessed_subject_participant_id",
            unique=True,
        ),
        Index("ix_whisper_guess_photo_guesser", "photo_id", "guesser_participant_id"),
        Index("ix_whisper_guess_photo_correct", "photo_id", postgresql_where=text("is_correct")),
    )


class WhisperDiscoveryStateModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "whisper_discovery_state"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    photo_id: Mapped[UUID] = mapped_column(
        ForeignKey("photo.id", ondelete="CASCADE"), nullable=False
    )
    total_guess_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    correct_guess_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    first_correct_guesser_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("participant.id", ondelete="SET NULL")
    )
    solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reveal_state: Mapped[DiscoveryRevealState] = mapped_column(
        _enum(DiscoveryRevealState, "discovery_reveal_state"),
        nullable=False,
        default=DiscoveryRevealState.hidden,
    )
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("uq_whisper_discovery_state_photo", "photo_id", unique=True),
        Index("ix_whisper_discovery_state_event", "event_id"),
    )
