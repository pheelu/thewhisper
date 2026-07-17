"""Entità di dominio della Foto Whisper."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from whisper.photo.core.enums import PhotoRemovalReason, PhotoStatus
from whisper.shared.core.entity import TimestampedEntity


@dataclass(kw_only=True)
class Photo(TimestampedEntity):
    event_id: UUID
    hunter_participant_id: UUID  # il Cacciatore — MAI esposto nei broadcast/feed
    subject_participant_id: UUID  # il Soggetto (risposta segreta)
    mysterious_title: str
    storage_key: str
    content_type: str
    status: PhotoStatus
    subject_revealed: bool
    revealed_at: datetime | None
    published_at: datetime | None
    removed_at: datetime | None
    removed_reason: PhotoRemovalReason | None
    removed_by_participant_id: UUID | None
    comment_count: int
    correct_guess_count: int
