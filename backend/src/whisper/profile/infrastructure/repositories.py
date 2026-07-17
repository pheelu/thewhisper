"""Implementazione SQLAlchemy del ProfileRepository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.profile.core.entities import Profile
from whisper.profile.infrastructure.models import ParticipantProfileModel


def _to_profile(row: ParticipantProfileModel) -> Profile:
    return Profile(
        id=row.id,
        event_id=row.event_id,
        participant_id=row.participant_id,
        secret_text=row.secret_text,
        motto=row.motto,
        avatar_seed=row.avatar_seed,
        accent_color=row.accent_color,
        clues=list(row.clues or []),
        reveal_stage=row.reveal_stage,
        is_complete=row.is_complete,
        completed_at=row.completed_at,
        disclosed_publicly_at=row.disclosed_publicly_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_participant(self, event_id: UUID, participant_id: UUID) -> Profile | None:
        stmt = select(ParticipantProfileModel).where(
            ParticipantProfileModel.event_id == event_id,
            ParticipantProfileModel.participant_id == participant_id,
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_profile(row) if row else None

    async def add(self, profile: Profile) -> None:
        self._s.add(
            ParticipantProfileModel(
                id=profile.id,
                event_id=profile.event_id,
                participant_id=profile.participant_id,
                secret_text=profile.secret_text,
                motto=profile.motto,
                avatar_seed=profile.avatar_seed,
                accent_color=profile.accent_color,
                clues=profile.clues,
                reveal_stage=profile.reveal_stage,
                is_complete=profile.is_complete,
                completed_at=profile.completed_at,
                disclosed_publicly_at=profile.disclosed_publicly_at,
                created_at=profile.created_at,
                updated_at=profile.updated_at,
            )
        )
        await self._s.flush()

    async def update(self, profile: Profile) -> None:
        obj = await self._s.get(ParticipantProfileModel, profile.id)
        if obj is None:
            return
        obj.secret_text = profile.secret_text
        obj.motto = profile.motto
        obj.avatar_seed = profile.avatar_seed
        obj.accent_color = profile.accent_color
        obj.clues = profile.clues
        obj.reveal_stage = profile.reveal_stage
        obj.is_complete = profile.is_complete
        obj.completed_at = profile.completed_at
        obj.disclosed_publicly_at = profile.disclosed_publicly_at
        obj.updated_at = profile.updated_at
