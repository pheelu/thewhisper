"""Query di lettura delle foto: feed, dettaglio, mie, di-me.

Espongono il Soggetto solo se rivelato (o sempre, nella vista del Cacciatore su
`/photos/mine`). Il Cacciatore NON è MAI incluso (discrezione). Restituiscono la
`storage_key` interna: il router la traduce in URL presigned e la rimuove.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_BASE_COLS = """
    ph.id, ph.mysterious_title, ph.storage_key, ph.published_at,
    ph.comment_count, ph.correct_guess_count, ph.subject_revealed,
    ph.subject_participant_id,
    sp.pseudonym AS subject_pseudonym, sp.noble_title AS subject_noble_title
"""

_FEED = text(
    f"""
    SELECT {_BASE_COLS}
    FROM photo ph
    LEFT JOIN participant sp ON sp.id = ph.subject_participant_id
    WHERE ph.event_id = :eid AND ph.status = 'published'
    ORDER BY ph.published_at DESC, ph.id DESC
    LIMIT :limit
    """
)

_ONE = text(
    f"""
    SELECT {_BASE_COLS}
    FROM photo ph
    LEFT JOIN participant sp ON sp.id = ph.subject_participant_id
    WHERE ph.event_id = :eid AND ph.id = :pid AND ph.status = 'published'
    """
)

_MINE = text(
    f"""
    SELECT {_BASE_COLS}
    FROM photo ph
    LEFT JOIN participant sp ON sp.id = ph.subject_participant_id
    WHERE ph.event_id = :eid AND ph.hunter_participant_id = :me
      AND ph.status <> 'removed'
    ORDER BY ph.created_at DESC
    """
)

_OF_ME = text(
    f"""
    SELECT {_BASE_COLS}
    FROM photo ph
    LEFT JOIN participant sp ON sp.id = ph.subject_participant_id
    WHERE ph.event_id = :eid AND ph.subject_participant_id = :me
      AND ph.status = 'published'
    ORDER BY ph.published_at DESC
    """
)


def _item(row: Any, *, always_show_subject: bool) -> dict[str, Any]:
    show = always_show_subject or row.subject_revealed
    return {
        "photo_id": str(row.id),
        "mysterious_title": row.mysterious_title,
        "storage_key": row.storage_key,  # rimossa dal router dopo il presign
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "comment_count": row.comment_count,
        "correct_guess_count": row.correct_guess_count,
        "subject_revealed": row.subject_revealed,
        "subject": (
            {
                "participant_id": str(row.subject_participant_id),
                "pseudonym": row.subject_pseudonym,
                "noble_title": row.subject_noble_title,
            }
            if show
            else None
        ),
    }


async def feed(session: AsyncSession, event_id: UUID, limit: int = 30) -> list[dict[str, Any]]:
    rows = (await session.execute(_FEED, {"eid": event_id, "limit": limit})).all()
    return [_item(r, always_show_subject=False) for r in rows]


async def detail(session: AsyncSession, event_id: UUID, photo_id: UUID) -> dict[str, Any] | None:
    row = (await session.execute(_ONE, {"eid": event_id, "pid": photo_id})).one_or_none()
    return _item(row, always_show_subject=False) if row else None


async def mine(session: AsyncSession, event_id: UUID, me: UUID) -> list[dict[str, Any]]:
    rows = (await session.execute(_MINE, {"eid": event_id, "me": me})).all()
    return [_item(r, always_show_subject=True) for r in rows]


async def of_me(session: AsyncSession, event_id: UUID, me: UUID) -> list[dict[str, Any]]:
    rows = (await session.execute(_OF_ME, {"eid": event_id, "me": me})).all()
    return [_item(r, always_show_subject=False) for r in rows]
