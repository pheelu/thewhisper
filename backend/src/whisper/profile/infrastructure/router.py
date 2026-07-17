"""Router HTTP del profilo: /profiles/me, /profiles, /profiles/{id}."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from whisper.gamification.infrastructure.points_service import PointsService
from whisper.profile.core import use_cases
from whisper.profile.infrastructure import queries
from whisper.profile.infrastructure.repositories import SqlAlchemyProfileRepository
from whisper.profile.infrastructure.schemas import (
    ProfileMe,
    UpdateProfileRequest,
    empty_profile_me,
    profile_me,
)
from whisper.shared.core.clock import SystemClock
from whisper.shared.core.errors import NotFoundError
from whisper.shared.core.events import DomainEvent
from whisper.shared.infrastructure.http.deps import Bus, CurrentParticipant, DbSession
from whisper.shared.infrastructure.realtime.broker import EventBus, RealtimeMessage

router = APIRouter(prefix="/api/v1/profiles", tags=["profile"])
_clock = SystemClock()


async def _publish(bus: EventBus, event_id: UUID, events: list[DomainEvent]) -> None:
    await bus.publish_many(
        [
            RealtimeMessage(
                event_id=event_id,
                type=e.type,
                payload=e.payload,
                target_participant_id=e.target_participant_id,
            )
            for e in events
        ]
    )


@router.get("/me", response_model=ProfileMe)
async def get_my_profile(db: DbSession, context: CurrentParticipant) -> ProfileMe:
    profile = await SqlAlchemyProfileRepository(db).get_by_participant(
        context.event_id, context.participant_id
    )
    return profile_me(profile) if profile else empty_profile_me(context.participant_id)


@router.put("/me", response_model=ProfileMe)
async def update_my_profile(
    body: UpdateProfileRequest, db: DbSession, context: CurrentParticipant, bus: Bus
) -> ProfileMe:
    profile, events = await use_cases.upsert_profile(
        SqlAlchemyProfileRepository(db),
        PointsService(db),
        _clock,
        event_id=context.event_id,
        participant_id=context.participant_id,
        secret_text=body.secret_text,
        motto=body.motto,
        accent_color=body.accent_color,
        avatar_seed=body.avatar_seed,
    )
    await db.commit()
    await _publish(bus, context.event_id, events)
    return profile_me(profile)


@router.get("")
async def get_roster(db: DbSession, context: CurrentParticipant) -> dict[str, Any]:
    return {"items": await queries.roster(db, context.event_id)}


@router.get("/{participant_id}")
async def get_profile(
    participant_id: UUID, db: DbSession, context: CurrentParticipant
) -> dict[str, Any]:
    profile = await queries.public_profile(
        db, context.event_id, participant_id, context.participant_id
    )
    if profile is None:
        raise NotFoundError("Profilo non trovato.", code="profile.not_found")
    return profile
