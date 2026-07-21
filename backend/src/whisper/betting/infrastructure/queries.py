"""Query di lettura delle scommesse (round corrente, pool per candidato, storico)."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_POOLS = text(
    """
    SELECT s.candidate_participant_id AS pid, p.pseudonym, sum(s.amount) AS pool,
           count(*) AS stakes
    FROM bet_stake s JOIN participant p ON p.id = s.candidate_participant_id
    WHERE s.round_id = :rid AND s.status <> 'cancelled'
    GROUP BY 1, 2 ORDER BY pool DESC
    """
)

_MY_STAKE = text(
    """
    SELECT s.id, s.candidate_participant_id, p.pseudonym AS candidate_pseudonym,
           s.amount, s.status, s.payout
    FROM bet_stake s JOIN participant p ON p.id = s.candidate_participant_id
    WHERE s.round_id = :rid AND s.participant_id = :me AND s.status <> 'cancelled'
    """
)

_RECENT_ROUNDS = text(
    """
    SELECT id, title, prompt, status, total_pool, settled_at, winning_candidate_ids,
           void_reason
    FROM bet_round
    WHERE event_id = :eid AND status IN ('settled', 'void')
    ORDER BY settled_at DESC NULLS LAST LIMIT :limit
    """
)

_NAMES = text("SELECT id, pseudonym FROM participant WHERE id = ANY(:ids)")


async def round_view(session: AsyncSession, round_row: Any, me: UUID) -> dict[str, Any]:
    pools = (await session.execute(_POOLS, {"rid": round_row.id})).all()
    my = (await session.execute(_MY_STAKE, {"rid": round_row.id, "me": me})).one_or_none()

    winners = None
    if round_row.winning_candidate_ids:
        rows = (
            await session.execute(_NAMES, {"ids": list(round_row.winning_candidate_ids)})
        ).all()
        winners = [{"participant_id": str(r.id), "pseudonym": r.pseudonym} for r in rows]

    return {
        "round_id": str(round_row.id),
        "title": round_row.title,
        "prompt": round_row.prompt,
        "status": str(round_row.status),
        "opens_at": round_row.opens_at.isoformat(),
        "closes_at": round_row.closes_at.isoformat(),
        "measurement_end": round_row.measurement_end.isoformat(),
        "min_stake": round_row.min_stake,
        "max_stake": round_row.max_stake,
        "total_pool": round_row.total_pool,
        "pools": [
            {
                "participant_id": str(p.pid),
                "pseudonym": p.pseudonym,
                "pool": int(p.pool),
                "stakes": int(p.stakes),
            }
            for p in pools
        ],
        "my_stake": (
            {
                "stake_id": str(my.id),
                "candidate_participant_id": str(my.candidate_participant_id),
                "candidate_pseudonym": my.candidate_pseudonym,
                "amount": my.amount,
                "status": my.status,
                "payout": my.payout,
            }
            if my
            else None
        ),
        "winners": winners,
        "void_reason": round_row.void_reason,
    }


async def recent_rounds(session: AsyncSession, event_id: UUID, limit: int = 10) -> list[dict]:
    rows = (await session.execute(_RECENT_ROUNDS, {"eid": event_id, "limit": limit})).all()
    out = []
    for r in rows:
        winners = None
        if r.winning_candidate_ids:
            names = (await session.execute(_NAMES, {"ids": list(r.winning_candidate_ids)})).all()
            winners = [n.pseudonym for n in names]
        out.append(
            {
                "round_id": str(r.id),
                "title": r.title,
                "status": str(r.status),
                "total_pool": r.total_pool,
                "settled_at": r.settled_at.isoformat() if r.settled_at else None,
                "winners": winners,
                "void_reason": r.void_reason,
            }
        )
    return out
