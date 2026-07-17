"""Implementazioni SQLAlchemy dei repository di identity (mapping ORM ↔ entità)."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.identity.core.entities import Event, Participant
from whisper.identity.infrastructure.models import EventModel, ParticipantModel
from whisper.shared.core.ids import uuid7


def _to_event(row: EventModel) -> Event:
    return Event(
        id=row.id,
        name=row.name,
        venue_name=row.venue_name,
        join_code=row.join_code,
        status=row.status,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        closed_at=row.closed_at,
        timezone=row.timezone,
        retention_until=row.retention_until,
        host_secret_hash=row.host_secret_hash,
        settings=dict(row.settings or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_participant(row: ParticipantModel) -> Participant:
    return Participant(
        id=row.id,
        event_id=row.event_id,
        pseudonym=row.pseudonym,
        noble_title=row.noble_title,
        role=row.role,
        score=row.score,
        is_photographable=row.is_photographable,
        consent_at=row.consent_at,
        consent_revoked_at=row.consent_revoked_at,
        session_token_id=row.session_token_id,
        last_seen_at=row.last_seen_at,
        left_at=row.left_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, event: Event) -> None:
        self._s.add(
            EventModel(
                id=event.id,
                name=event.name,
                venue_name=event.venue_name,
                join_code=event.join_code,
                status=event.status,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                closed_at=event.closed_at,
                timezone=event.timezone,
                retention_until=event.retention_until,
                host_secret_hash=event.host_secret_hash,
                settings=event.settings,
                created_at=event.created_at,
                updated_at=event.updated_at,
            )
        )
        await self._s.flush()

    async def get(self, event_id: UUID) -> Event | None:
        row = await self._s.get(EventModel, event_id)
        return _to_event(row) if row else None

    async def get_by_join_code(self, join_code: str) -> Event | None:
        stmt = select(EventModel).where(func.lower(EventModel.join_code) == join_code.lower())
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_event(row) if row else None

    async def update(self, event: Event) -> None:
        obj = await self._s.get(EventModel, event.id)
        if obj is None:
            return
        obj.name = event.name
        obj.venue_name = event.venue_name
        obj.status = event.status
        obj.closed_at = event.closed_at
        obj.retention_until = event.retention_until
        obj.settings = event.settings
        obj.updated_at = event.updated_at


class SqlAlchemyParticipantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, participant: Participant) -> None:
        self._s.add(
            ParticipantModel(
                id=participant.id,
                event_id=participant.event_id,
                pseudonym=participant.pseudonym,
                noble_title=participant.noble_title,
                role=participant.role,
                score=participant.score,
                is_photographable=participant.is_photographable,
                consent_at=participant.consent_at,
                consent_revoked_at=participant.consent_revoked_at,
                session_token_id=participant.session_token_id,
                last_seen_at=participant.last_seen_at,
                left_at=participant.left_at,
                created_at=participant.created_at,
                updated_at=participant.updated_at,
            )
        )
        await self._s.flush()

    async def get(self, event_id: UUID, participant_id: UUID) -> Participant | None:
        stmt = select(ParticipantModel).where(
            ParticipantModel.id == participant_id, ParticipantModel.event_id == event_id
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_participant(row) if row else None

    async def get_host(self, event_id: UUID) -> Participant | None:
        stmt = (
            select(ParticipantModel)
            .where(ParticipantModel.event_id == event_id, ParticipantModel.role == "host")
            .order_by(ParticipantModel.created_at.asc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_participant(row) if row else None

    async def get_by_pseudonym(self, event_id: UUID, pseudonym: str) -> Participant | None:
        stmt = select(ParticipantModel).where(
            ParticipantModel.event_id == event_id,
            func.lower(ParticipantModel.pseudonym) == pseudonym.lower(),
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_participant(row) if row else None

    async def update(self, participant: Participant) -> None:
        obj = await self._s.get(ParticipantModel, participant.id)
        if obj is None:
            return
        obj.pseudonym = participant.pseudonym
        obj.noble_title = participant.noble_title
        obj.score = participant.score
        obj.is_photographable = participant.is_photographable
        obj.consent_at = participant.consent_at
        obj.consent_revoked_at = participant.consent_revoked_at
        obj.session_token_id = participant.session_token_id
        obj.last_seen_at = participant.last_seen_at
        obj.left_at = participant.left_at
        obj.updated_at = participant.updated_at

    async def rotate_all_session_tokens(self, event_id: UUID) -> None:
        await self._s.execute(
            update(ParticipantModel)
            .where(ParticipantModel.event_id == event_id)
            .values(session_token_id=uuid7())
        )
