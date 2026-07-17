"""Porta `PhotoPort`: consente a `discovery` di validare i guess e aggiornare i
contatori denormalizzati della foto, senza importare i modelli ORM di `photo`."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from whisper.photo.core.enums import PhotoStatus


@dataclass(frozen=True)
class PhotoContext:
    """Vista minimale della foto per la meccanica di scoperta."""

    photo_id: UUID
    hunter_participant_id: UUID
    subject_participant_id: UUID
    status: PhotoStatus


class PhotoPort(Protocol):
    async def get_context(self, event_id: UUID, photo_id: UUID) -> PhotoContext | None: ...
    async def bump_comment_count(self, photo_id: UUID, delta: int) -> int: ...
    async def bump_correct_guess_count(self, photo_id: UUID, delta: int) -> int: ...
