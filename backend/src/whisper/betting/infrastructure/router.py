"""Router HTTP delle scommesse."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from whisper.betting.core.enums import BetRoundStatus
from whisper.betting.infrastructure import queries
from whisper.betting.infrastructure.service import BettingService
from whisper.shared.core.clock import SystemClock
from whisper.shared.core.errors import ForbiddenError, NotFoundError
from whisper.shared.core.events import DomainEvent
from whisper.shared.infrastructure.http.deps import Bus, CurrentParticipant, DbSession
from whisper.shared.infrastructure.realtime.broker import EventBus, RealtimeMessage

router = APIRouter(prefix="/api/v1/bets", tags=["betting"])
_clock = SystemClock()


class PlaceStakeRequest(BaseModel):
    candidate_participant_id: UUID
    amount: int = Field(ge=1, le=1000)


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


@router.get("/rounds/current")
async def current_round(db: DbSession, context: CurrentParticipant, bus: Bus) -> dict[str, Any]:
    svc = BettingService(db)
    now = _clock.now()
    # tick "pigro": la lettura fa avanzare lo stato se lo scheduler non è ancora passato
    events = await svc.tick(context.event_id, now)
    if events:
        await db.commit()
        await _publish(bus, context.event_id, events)
    round_ = await svc.get_active_round(context.event_id)
    if round_ is None:
        return {"round": None}
    return {"round": await queries.round_view(db, round_, context.participant_id)}


@router.get("/rounds")
async def list_rounds(db: DbSession, context: CurrentParticipant) -> dict[str, Any]:
    return {"items": await queries.recent_rounds(db, context.event_id)}


@router.post("/rounds/{round_id}/stakes", status_code=status.HTTP_201_CREATED)
async def place_stake(
    round_id: UUID,
    body: PlaceStakeRequest,
    db: DbSession,
    context: CurrentParticipant,
    bus: Bus,
) -> dict[str, Any]:
    svc = BettingService(db)
    stake, events = await svc.place_stake(
        event_id=context.event_id,
        round_id=round_id,
        participant_id=context.participant_id,
        candidate_id=body.candidate_participant_id,
        amount=body.amount,
        now=_clock.now(),
    )
    await db.commit()
    await _publish(bus, context.event_id, events)
    return {"stake_id": str(stake.id), "amount": stake.amount}


@router.delete("/stakes/{stake_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_stake(
    stake_id: UUID, db: DbSession, context: CurrentParticipant, bus: Bus
):
    svc = BettingService(db)
    events = await svc.cancel_stake(
        event_id=context.event_id,
        stake_id=stake_id,
        participant_id=context.participant_id,
        now=_clock.now(),
    )
    await db.commit()
    await _publish(bus, context.event_id, events)


# ---------- host ----------
@router.post("/rounds", status_code=status.HTTP_201_CREATED)
async def host_create_round(db: DbSession, context: CurrentParticipant, bus: Bus) -> dict[str, Any]:
    if not context.is_host:
        raise ForbiddenError("Operazione riservata all'organizzatore.", code="session.not_host")
    svc = BettingService(db)
    round_, events = await svc.create_round(context.event_id, _clock.now())
    await db.commit()
    await _publish(bus, context.event_id, events)
    return {"round_id": str(round_.id), "title": round_.title}


@router.post("/rounds/{round_id}/lock")
async def host_lock(round_id: UUID, db: DbSession, context: CurrentParticipant, bus: Bus) -> dict:
    if not context.is_host:
        raise ForbiddenError("Operazione riservata all'organizzatore.", code="session.not_host")
    svc = BettingService(db)
    round_ = await svc._get_round(context.event_id, round_id)
    events = await svc.lock_round(round_, _clock.now())
    await db.commit()
    await _publish(bus, context.event_id, events)
    return {"status": str(round_.status)}


@router.post("/rounds/{round_id}/settle")
async def host_settle(round_id: UUID, db: DbSession, context: CurrentParticipant, bus: Bus) -> dict:
    if not context.is_host:
        raise ForbiddenError("Operazione riservata all'organizzatore.", code="session.not_host")
    svc = BettingService(db)
    round_ = await svc._get_round(context.event_id, round_id)
    if round_.status not in (BetRoundStatus.open, BetRoundStatus.locked):
        raise NotFoundError("Round non risolvibile.", code="betting.not_settleable")
    now = _clock.now()
    events = await svc.lock_round(round_, now)
    events.extend(await svc.settle_round(round_, now))
    await db.commit()
    await _publish(bus, context.event_id, events)
    return {"status": str(round_.status)}
