"""Query di lettura di gamification (classifica, saldo, movimenti).

Leggono `participant`/`point_ledger` via SQL grezzo per non importare i modelli ORM
del dominio identity (rispetto del layering).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_LEADERBOARD = text(
    """
    SELECT id, pseudonym, noble_title, score
    FROM participant
    WHERE event_id = :eid AND role = 'guest' AND left_at IS NULL
    ORDER BY score DESC, created_at ASC
    LIMIT :limit
    """
)

_RECENT = text(
    """
    SELECT delta, reason, source_domain, metadata, created_at
    FROM point_ledger
    WHERE event_id = :eid AND participant_id = :pid
    ORDER BY created_at DESC, id DESC
    LIMIT :limit
    """
)


async def leaderboard(
    session: AsyncSession, event_id: UUID, limit: int = 20
) -> list[dict[str, Any]]:
    rows = (await session.execute(_LEADERBOARD, {"eid": event_id, "limit": limit})).all()
    return [
        {
            "rank": i + 1,
            "participant_id": str(r.id),
            "pseudonym": r.pseudonym,
            "noble_title": r.noble_title,
            "score": r.score,
        }
        for i, r in enumerate(rows)
    ]


async def recent_movements(
    session: AsyncSession, event_id: UUID, participant_id: UUID, limit: int = 20
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(_RECENT, {"eid": event_id, "pid": participant_id, "limit": limit})
    ).all()
    return [
        {
            "delta": r.delta,
            "reason": r.reason,
            "source_domain": r.source_domain,
            "metadata": r.metadata,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
