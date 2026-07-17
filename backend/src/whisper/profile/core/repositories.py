"""Porta di persistenza del profilo (Protocol)."""

from typing import Protocol
from uuid import UUID

from whisper.profile.core.entities import Profile


class ProfileRepository(Protocol):
    async def get_by_participant(self, event_id: UUID, participant_id: UUID) -> Profile | None: ...
    async def add(self, profile: Profile) -> None: ...
    async def update(self, profile: Profile) -> None: ...
