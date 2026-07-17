"""Implementazione SQLAlchemy del PhotoRepository."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.photo.core.entities import Photo
from whisper.photo.core.repositories import SubjectState
from whisper.photo.infrastructure.models import PhotoModel

_SUBJECT_STATE = text(
    """
    SELECT role, is_photographable, (consent_at IS NOT NULL) AS has_consent
    FROM participant WHERE event_id = :eid AND id = :pid
    """
)


def _to_photo(row: PhotoModel) -> Photo:
    return Photo(
        id=row.id,
        event_id=row.event_id,
        hunter_participant_id=row.hunter_participant_id,
        subject_participant_id=row.subject_participant_id,
        mysterious_title=row.mysterious_title,
        storage_key=row.storage_key,
        content_type=row.content_type,
        status=row.status,
        subject_revealed=row.subject_revealed,
        revealed_at=row.revealed_at,
        published_at=row.published_at,
        removed_at=row.removed_at,
        removed_reason=row.removed_reason,
        removed_by_participant_id=row.removed_by_participant_id,
        comment_count=row.comment_count,
        correct_guess_count=row.correct_guess_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyPhotoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, photo: Photo) -> None:
        self._s.add(
            PhotoModel(
                id=photo.id,
                event_id=photo.event_id,
                hunter_participant_id=photo.hunter_participant_id,
                subject_participant_id=photo.subject_participant_id,
                mysterious_title=photo.mysterious_title,
                storage_key=photo.storage_key,
                content_type=photo.content_type,
                status=photo.status,
                subject_revealed=photo.subject_revealed,
                revealed_at=photo.revealed_at,
                published_at=photo.published_at,
                removed_at=photo.removed_at,
                removed_reason=photo.removed_reason,
                removed_by_participant_id=photo.removed_by_participant_id,
                comment_count=photo.comment_count,
                correct_guess_count=photo.correct_guess_count,
                created_at=photo.created_at,
                updated_at=photo.updated_at,
            )
        )
        await self._s.flush()

    async def get(self, event_id: UUID, photo_id: UUID) -> Photo | None:
        stmt = select(PhotoModel).where(
            PhotoModel.id == photo_id, PhotoModel.event_id == event_id
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_photo(row) if row else None

    async def update(self, photo: Photo) -> None:
        obj = await self._s.get(PhotoModel, photo.id)
        if obj is None:
            return
        obj.mysterious_title = photo.mysterious_title
        obj.status = photo.status
        obj.subject_revealed = photo.subject_revealed
        obj.revealed_at = photo.revealed_at
        obj.published_at = photo.published_at
        obj.removed_at = photo.removed_at
        obj.removed_reason = photo.removed_reason
        obj.removed_by_participant_id = photo.removed_by_participant_id
        obj.comment_count = photo.comment_count
        obj.correct_guess_count = photo.correct_guess_count
        obj.updated_at = photo.updated_at

    async def get_subject_state(self, event_id: UUID, subject_id: UUID) -> SubjectState | None:
        row = (
            await self._s.execute(_SUBJECT_STATE, {"eid": event_id, "pid": subject_id})
        ).one_or_none()
        if row is None:
            return None
        return SubjectState(
            is_guest=row.role == "guest",
            is_photographable=row.is_photographable,
            has_consent=row.has_consent,
        )
