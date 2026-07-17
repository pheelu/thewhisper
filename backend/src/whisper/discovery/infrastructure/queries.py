"""Query di lettura della scoperta: commenti, i miei guess, stato di scoperta."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_COMMENTS = text(
    """
    SELECT c.id, c.author_participant_id, a.pseudonym AS author_pseudonym,
           a.noble_title AS author_noble_title, c.body, c.created_at
    FROM whisper_comment c
    LEFT JOIN participant a ON a.id = c.author_participant_id
    WHERE c.event_id = :eid AND c.photo_id = :ph AND c.status = 'visible'
    ORDER BY c.created_at ASC
    LIMIT :limit
    """
)

_MY_GUESSES = text(
    """
    SELECT guessed_subject_participant_id, is_correct, created_at
    FROM whisper_guess
    WHERE photo_id = :ph AND guesser_participant_id = :g
    ORDER BY created_at ASC
    """
)

_STATE = text(
    """
    SELECT total_guess_count, correct_guess_count, solved_at, reveal_state
    FROM whisper_discovery_state WHERE event_id = :eid AND photo_id = :ph
    """
)


async def comments(
    session: AsyncSession, event_id: UUID, photo_id: UUID, limit: int = 100
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(_COMMENTS, {"eid": event_id, "ph": photo_id, "limit": limit})
    ).all()
    return [
        {
            "comment_id": str(r.id),
            "author_participant_id": str(r.author_participant_id) if r.author_participant_id else None,
            "author_pseudonym": r.author_pseudonym,
            "author_noble_title": r.author_noble_title,
            "body": r.body,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


async def my_guesses(
    session: AsyncSession, photo_id: UUID, guesser_id: UUID
) -> list[dict[str, Any]]:
    rows = (await session.execute(_MY_GUESSES, {"ph": photo_id, "g": guesser_id})).all()
    return [
        {
            "guessed_subject_participant_id": str(r.guessed_subject_participant_id),
            "is_correct": r.is_correct,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


async def discovery_state(
    session: AsyncSession, event_id: UUID, photo_id: UUID
) -> dict[str, Any]:
    row = (await session.execute(_STATE, {"eid": event_id, "ph": photo_id})).one_or_none()
    if row is None:
        return {
            "total_guess_count": 0,
            "correct_guess_count": 0,
            "solved_at": None,
            "reveal_state": "hidden",
        }
    return {
        "total_guess_count": row.total_guess_count,
        "correct_guess_count": row.correct_guess_count,
        "solved_at": row.solved_at.isoformat() if row.solved_at else None,
        "reveal_state": row.reveal_state,
    }
