"""Router HTTP della scoperta: commenti e guess sotto /api/v1/photos/{photo_id}."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from whisper.discovery.core import use_cases
from whisper.discovery.infrastructure import queries
from whisper.discovery.infrastructure.repositories import SqlAlchemyDiscoveryRepository
from whisper.discovery.infrastructure.schemas import (
    CommentRequest,
    GuessRequest,
    GuessResponse,
)
from whisper.gamification.infrastructure.points_service import PointsService
from whisper.photo.infrastructure.photo_port import PhotoService
from whisper.shared.core.clock import SystemClock
from whisper.shared.core.events import DomainEvent
from whisper.shared.infrastructure.http.deps import Bus, CurrentParticipant, DbSession
from whisper.shared.infrastructure.realtime.broker import EventBus, RealtimeMessage

router = APIRouter(prefix="/api/v1/photos", tags=["discovery"])
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


@router.post("/{photo_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    photo_id: UUID, body: CommentRequest, db: DbSession, context: CurrentParticipant, bus: Bus
) -> dict[str, Any]:
    comment, events = await use_cases.add_comment(
        SqlAlchemyDiscoveryRepository(db),
        PhotoService(db),
        _clock,
        event_id=context.event_id,
        photo_id=photo_id,
        author_id=context.participant_id,
        body=body.body,
    )
    await db.commit()
    await _publish(bus, context.event_id, events)
    return {
        "comment_id": str(comment.id),
        "body": comment.body,
        "created_at": comment.created_at.isoformat(),
    }


@router.get("/{photo_id}/comments")
async def list_comments(
    photo_id: UUID,
    db: DbSession,
    context: CurrentParticipant,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    return {"items": await queries.comments(db, context.event_id, photo_id, limit=limit)}


@router.post("/{photo_id}/guesses", response_model=GuessResponse)
async def submit_guess(
    photo_id: UUID, body: GuessRequest, db: DbSession, context: CurrentParticipant, bus: Bus
) -> GuessResponse:
    outcome = await use_cases.submit_guess(
        SqlAlchemyDiscoveryRepository(db),
        PhotoService(db),
        PointsService(db),
        _clock,
        event_id=context.event_id,
        photo_id=photo_id,
        guesser_id=context.participant_id,
        candidate_id=body.guessed_subject_participant_id,
    )
    await db.commit()
    await _publish(bus, context.event_id, outcome.events)
    return GuessResponse(
        is_correct=outcome.is_correct,
        guess_rank=outcome.guess_rank,
        points_awarded=outcome.points_awarded,
        attempts_left=outcome.attempts_left,
    )


@router.get("/{photo_id}/guesses/me")
async def my_guesses(
    photo_id: UUID, db: DbSession, context: CurrentParticipant
) -> dict[str, Any]:
    return {"items": await queries.my_guesses(db, photo_id, context.participant_id)}


@router.get("/{photo_id}/discovery")
async def get_discovery(
    photo_id: UUID, db: DbSession, context: CurrentParticipant
) -> dict[str, Any]:
    return await queries.discovery_state(db, context.event_id, photo_id)
