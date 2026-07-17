"""Modello ORM della Foto Whisper: tabella `photo`."""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from whisper.photo.core.enums import PhotoRemovalReason, PhotoStatus
from whisper.shared.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


class PhotoModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "photo"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    hunter_participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    subject_participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    mysterious_title: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="image/jpeg", server_default="image/jpeg"
    )
    status: Mapped[PhotoStatus] = mapped_column(
        _enum(PhotoStatus, "photo_status"), nullable=False, default=PhotoStatus.draft
    )
    subject_revealed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_reason: Mapped[PhotoRemovalReason | None] = mapped_column(
        _enum(PhotoRemovalReason, "photo_removal_reason")
    )
    removed_by_participant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("participant.id", ondelete="SET NULL")
    )
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    correct_guess_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    __table_args__ = (
        Index("uq_photo_storage_key", "storage_key", unique=True),
        Index("ix_photo_feed", "event_id", "status", "published_at", "id"),
        Index("ix_photo_hunter", "event_id", "hunter_participant_id"),
        Index("ix_photo_subject", "event_id", "subject_participant_id"),
        CheckConstraint(
            "hunter_participant_id <> subject_participant_id", name="hunter_not_subject"
        ),
        CheckConstraint(
            "char_length(mysterious_title) BETWEEN 1 AND 120", name="title_len"
        ),
        CheckConstraint(
            "content_type IN ('image/jpeg','image/png','image/webp')", name="content_type"
        ),
    )
