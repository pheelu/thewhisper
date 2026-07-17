"""Implementazione SQLAlchemy del DiscoveryRepository."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.discovery.core.entities import Comment, Guess
from whisper.discovery.core.enums import DiscoveryRevealState
from whisper.discovery.infrastructure.models import (
    WhisperCommentModel,
    WhisperDiscoveryStateModel,
    WhisperGuessModel,
)
from whisper.shared.core.ids import uuid7

_IS_GUEST = text(
    "SELECT 1 FROM participant "
    "WHERE event_id = :eid AND id = :pid AND role = 'guest' AND left_at IS NULL"
)
_ATTEMPTS = text(
    "SELECT count(*) FROM whisper_guess WHERE photo_id = :ph AND guesser_participant_id = :g"
)
_HAS_CORRECT = text(
    "SELECT EXISTS(SELECT 1 FROM whisper_guess "
    "WHERE photo_id = :ph AND guesser_participant_id = :g AND is_correct)"
)
_HAS_CANDIDATE = text(
    "SELECT EXISTS(SELECT 1 FROM whisper_guess WHERE photo_id = :ph "
    "AND guesser_participant_id = :g AND guessed_subject_participant_id = :c)"
)
_DISTINCT_CORRECT = text(
    "SELECT count(DISTINCT guesser_participant_id) FROM whisper_guess "
    "WHERE photo_id = :ph AND is_correct"
)


class SqlAlchemyDiscoveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add_comment(self, comment: Comment) -> None:
        self._s.add(
            WhisperCommentModel(
                id=comment.id,
                event_id=comment.event_id,
                photo_id=comment.photo_id,
                author_participant_id=comment.author_participant_id,
                body=comment.body,
                status=comment.status,
                created_at=comment.created_at,
            )
        )
        await self._s.flush()

    async def add_guess(self, guess: Guess) -> None:
        self._s.add(
            WhisperGuessModel(
                id=guess.id,
                event_id=guess.event_id,
                photo_id=guess.photo_id,
                guesser_participant_id=guess.guesser_participant_id,
                guessed_subject_participant_id=guess.guessed_subject_participant_id,
                is_correct=guess.is_correct,
                guess_rank=guess.guess_rank,
                created_at=guess.created_at,
            )
        )
        await self._s.flush()

    async def candidate_is_guest(self, event_id: UUID, candidate_id: UUID) -> bool:
        row = (await self._s.execute(_IS_GUEST, {"eid": event_id, "pid": candidate_id})).first()
        return row is not None

    async def attempts_by(self, photo_id: UUID, guesser_id: UUID) -> int:
        return int(
            (await self._s.execute(_ATTEMPTS, {"ph": photo_id, "g": guesser_id})).scalar_one()
        )

    async def has_correct_by(self, photo_id: UUID, guesser_id: UUID) -> bool:
        return bool(
            (await self._s.execute(_HAS_CORRECT, {"ph": photo_id, "g": guesser_id})).scalar_one()
        )

    async def has_guessed_candidate(
        self, photo_id: UUID, guesser_id: UUID, candidate_id: UUID
    ) -> bool:
        return bool(
            (
                await self._s.execute(
                    _HAS_CANDIDATE, {"ph": photo_id, "g": guesser_id, "c": candidate_id}
                )
            ).scalar_one()
        )

    async def distinct_correct_guessers(self, photo_id: UUID) -> int:
        return int((await self._s.execute(_DISTINCT_CORRECT, {"ph": photo_id})).scalar_one())

    async def upsert_state(
        self,
        *,
        event_id: UUID,
        photo_id: UUID,
        is_correct: bool,
        guesser_id: UUID,
        now: datetime,
    ) -> None:
        stmt = pg_insert(WhisperDiscoveryStateModel).values(
            id=uuid7(),
            event_id=event_id,
            photo_id=photo_id,
            total_guess_count=1,
            correct_guess_count=1 if is_correct else 0,
            first_correct_guesser_id=guesser_id if is_correct else None,
            solved_at=now if is_correct else None,
            reveal_state=DiscoveryRevealState.hidden,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["photo_id"],
            set_={
                "total_guess_count": WhisperDiscoveryStateModel.total_guess_count + 1,
                "correct_guess_count": WhisperDiscoveryStateModel.correct_guess_count
                + (1 if is_correct else 0),
                "first_correct_guesser_id": func.coalesce(
                    WhisperDiscoveryStateModel.first_correct_guesser_id,
                    stmt.excluded.first_correct_guesser_id,
                ),
                "solved_at": func.coalesce(
                    WhisperDiscoveryStateModel.solved_at, stmt.excluded.solved_at
                ),
                "updated_at": now,
            },
        )
        await self._s.execute(stmt)
