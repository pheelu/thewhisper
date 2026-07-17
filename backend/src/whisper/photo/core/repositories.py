"""Porta di persistenza delle foto (Protocol) + stato del Soggetto per il gate consenso."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from whisper.photo.core.entities import Photo


@dataclass(frozen=True)
class SubjectState:
    is_guest: bool
    is_photographable: bool
    has_consent: bool

    @property
    def can_be_photographed(self) -> bool:
        return self.is_guest and self.is_photographable and self.has_consent


class PhotoRepository(Protocol):
    async def add(self, photo: Photo) -> None: ...
    async def get(self, event_id: UUID, photo_id: UUID) -> Photo | None: ...
    async def update(self, photo: Photo) -> None: ...
    async def get_subject_state(self, event_id: UUID, subject_id: UUID) -> SubjectState | None: ...
