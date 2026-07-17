"""Router HTTP di gamification: classifica e saldo punti del partecipante."""

from typing import Any

from fastapi import APIRouter, Query

from whisper.gamification.infrastructure import queries
from whisper.gamification.infrastructure.points_service import PointsService
from whisper.shared.infrastructure.http.deps import CurrentParticipant, DbSession

router = APIRouter(prefix="/api/v1", tags=["gamification"])


@router.get("/leaderboard")
async def get_leaderboard(
    db: DbSession, context: CurrentParticipant, limit: int = Query(default=20, ge=1, le=100)
) -> dict[str, Any]:
    items = await queries.leaderboard(db, context.event_id, limit=limit)
    return {"items": items}


@router.get("/me/points")
async def my_points(
    db: DbSession, context: CurrentParticipant, limit: int = Query(default=20, ge=1, le=100)
) -> dict[str, Any]:
    balance = await PointsService(db).get_balance(
        event_id=context.event_id, participant_id=context.participant_id
    )
    recent = await queries.recent_movements(db, context.event_id, context.participant_id, limit=limit)
    return {"balance": balance, "recent": recent}
