"""Porta di persistenza della scoperta (Protocol)."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from whisper.discovery.core.entities import Comment, Guess


class DiscoveryRepository(Protocol):
    async def lock_photo_discovery(self, photo_id: UUID) -> None:
        """Serializza i guess concorrenti sulla stessa foto (rank corretti)."""
        ...

    async def add_comment(self, comment: Comment) -> None: ...
    async def add_guess(self, guess: Guess) -> None: ...
    async def candidate_is_guest(self, event_id: UUID, candidate_id: UUID) -> bool: ...
    async def attempts_by(self, photo_id: UUID, guesser_id: UUID) -> int: ...
    async def has_correct_by(self, photo_id: UUID, guesser_id: UUID) -> bool: ...
    async def has_guessed_candidate(
        self, photo_id: UUID, guesser_id: UUID, candidate_id: UUID
    ) -> bool: ...
    async def distinct_correct_guessers(self, photo_id: UUID) -> int: ...
    async def upsert_state(
        self,
        *,
        event_id: UUID,
        photo_id: UUID,
        is_correct: bool,
        guesser_id: UUID,
        now: datetime,
    ) -> None: ...
