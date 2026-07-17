"""Implementazione di `PhotoPort` (consumata da `discovery`)."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.photo.core.enums import PhotoStatus
from whisper.photo.core.ports import PhotoContext

_CONTEXT = text(
    """
    SELECT hunter_participant_id, subject_participant_id, status
    FROM photo WHERE event_id = :eid AND id = :pid
    """
)
_BUMP_COMMENT = text(
    "UPDATE photo SET comment_count = comment_count + :d, updated_at = now() "
    "WHERE id = :pid RETURNING comment_count"
)
_BUMP_CORRECT = text(
    "UPDATE photo SET correct_guess_count = correct_guess_count + :d, updated_at = now() "
    "WHERE id = :pid RETURNING correct_guess_count"
)


class PhotoService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_context(self, event_id: UUID, photo_id: UUID) -> PhotoContext | None:
        row = (await self._s.execute(_CONTEXT, {"eid": event_id, "pid": photo_id})).one_or_none()
        if row is None:
            return None
        return PhotoContext(
            photo_id=photo_id,
            hunter_participant_id=row.hunter_participant_id,
            subject_participant_id=row.subject_participant_id,
            status=PhotoStatus(row.status),
        )

    async def bump_comment_count(self, photo_id: UUID, delta: int) -> int:
        return (await self._s.execute(_BUMP_COMMENT, {"d": delta, "pid": photo_id})).scalar_one()

    async def bump_correct_guess_count(self, photo_id: UUID, delta: int) -> int:
        return (await self._s.execute(_BUMP_CORRECT, {"d": delta, "pid": photo_id})).scalar_one()
