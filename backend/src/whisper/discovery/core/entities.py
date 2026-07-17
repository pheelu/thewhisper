"""Entità di dominio della scoperta: commento e tentativo di indovinare."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from whisper.discovery.core.enums import CommentStatus
from whisper.shared.core.entity import BaseEntity


@dataclass(kw_only=True)
class Comment(BaseEntity):
    event_id: UUID
    photo_id: UUID
    author_participant_id: UUID | None
    body: str
    status: CommentStatus
    created_at: datetime


@dataclass(kw_only=True)
class Guess(BaseEntity):
    event_id: UUID
    photo_id: UUID
    guesser_participant_id: UUID
    guessed_subject_participant_id: UUID
    is_correct: bool
    guess_rank: int | None
    created_at: datetime
