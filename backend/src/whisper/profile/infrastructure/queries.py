"""Query di lettura del profilo: roster della serata e scheda pubblica.

Legge `participant` (+ `participant_profile` in LEFT JOIN) via SQL grezzo per non
importare i modelli ORM di identity.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ROSTER = text(
    """
    SELECT p.id, p.pseudonym, p.noble_title, p.score, p.is_photographable,
           pr.motto, pr.avatar_seed, pr.accent_color, pr.reveal_stage
    FROM participant p
    LEFT JOIN participant_profile pr ON pr.participant_id = p.id
    WHERE p.event_id = :eid AND p.role = 'guest' AND p.left_at IS NULL
    ORDER BY p.created_at ASC
    """
)

_ONE = text(
    """
    SELECT p.id, p.pseudonym, p.noble_title, p.score, p.is_photographable,
           pr.secret_text, pr.motto, pr.avatar_seed, pr.accent_color,
           pr.reveal_stage, pr.disclosed_publicly_at
    FROM participant p
    LEFT JOIN participant_profile pr ON pr.participant_id = p.id
    WHERE p.event_id = :eid AND p.id = :pid
    """
)


def _avatar(pid: str, seed: str | None) -> str:
    return seed or pid.replace("-", "")[:12]


async def roster(session: AsyncSession, event_id: UUID) -> list[dict[str, Any]]:
    rows = (await session.execute(_ROSTER, {"eid": event_id})).all()
    return [
        {
            "participant_id": str(r.id),
            "pseudonym": r.pseudonym,
            "noble_title": r.noble_title,
            "score": r.score,
            "is_photographable": r.is_photographable,
            "motto": r.motto,
            "avatar_seed": _avatar(str(r.id), r.avatar_seed),
            "accent_color": r.accent_color,
            "reveal_stage": r.reveal_stage or "concealed",
        }
        for r in rows
    ]


async def public_profile(
    session: AsyncSession, event_id: UUID, participant_id: UUID, viewer_id: UUID
) -> dict[str, Any] | None:
    row = (await session.execute(_ONE, {"eid": event_id, "pid": participant_id})).one_or_none()
    if row is None:
        return None
    is_self = participant_id == viewer_id
    disclosed = row.disclosed_publicly_at is not None
    return {
        "participant_id": str(row.id),
        "pseudonym": row.pseudonym,
        "noble_title": row.noble_title,
        "score": row.score,
        "is_photographable": row.is_photographable,
        "motto": row.motto,
        "avatar_seed": _avatar(str(row.id), row.avatar_seed),
        "accent_color": row.accent_color,
        "reveal_stage": row.reveal_stage or "concealed",
        # Il segreto è visibile solo a se stessi o se l'identità è stata svelata.
        "secret_text": row.secret_text if (is_self or disclosed) else None,
    }
