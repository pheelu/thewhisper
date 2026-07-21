"""Query di lettura del dialogo, con la regola di mascheramento applicata.

Il nome mostrato del mittente della missiva è l'alias finché non si rivela;
lo pseudonimo reale non lascia MAI il server prima del reveal.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_LIST = text(
    """
    SELECT c.id, c.initiator_id, c.recipient_id, c.initiator_alias,
           c.initiator_revealed, c.contact_exchanged_at, c.last_message_at,
           c.initiator_contact_consent, c.recipient_contact_consent,
           c.initiator_last_read_at, c.recipient_last_read_at, c.status,
           pi.pseudonym AS initiator_pseudonym, pi.noble_title AS initiator_title,
           pr.pseudonym AS recipient_pseudonym, pr.noble_title AS recipient_title,
           (SELECT m.body FROM dialogue_message m
             WHERE m.conversation_id = c.id AND m.kind = 'text'
             ORDER BY m.created_at DESC LIMIT 1) AS last_body,
           (SELECT count(*) FROM dialogue_message m
             WHERE m.conversation_id = c.id AND m.kind = 'text'
               AND m.sender_id <> :me
               AND m.created_at > COALESCE(
                     CASE WHEN c.initiator_id = :me
                          THEN c.initiator_last_read_at
                          ELSE c.recipient_last_read_at END,
                     'epoch'::timestamptz)) AS unread_count
    FROM conversation c
    JOIN participant pi ON pi.id = c.initiator_id
    JOIN participant pr ON pr.id = c.recipient_id
    WHERE c.event_id = :eid AND (c.initiator_id = :me OR c.recipient_id = :me)
    ORDER BY c.last_message_at DESC NULLS LAST
    """
)

_MESSAGES = text(
    """
    SELECT m.id, m.sender_id, m.kind, m.body, m.created_at
    FROM dialogue_message m
    WHERE m.event_id = :eid AND m.conversation_id = :cid
    ORDER BY m.created_at ASC
    LIMIT :limit
    """
)


def _counterpart_display(row: Any, me: UUID) -> dict[str, Any]:
    """Come il viewer vede l'altra parte (mascheramento incluso)."""
    if row.initiator_id == me:
        # io sono il mittente: vedo il destinatario in chiaro
        return {
            "display_name": row.recipient_pseudonym,
            "noble_title": row.recipient_title,
            "is_masked": False,
        }
    # io sono il destinatario: vedo l'alias finché il mittente non si rivela
    if row.initiator_revealed:
        return {
            "display_name": row.initiator_pseudonym,
            "noble_title": row.initiator_title,
            "is_masked": False,
        }
    return {"display_name": row.initiator_alias, "noble_title": None, "is_masked": True}


async def conversations_for(
    session: AsyncSession, event_id: UUID, me: UUID
) -> list[dict[str, Any]]:
    rows = (await session.execute(_LIST, {"eid": event_id, "me": me})).all()
    items = []
    for r in rows:
        i_am_initiator = r.initiator_id == me
        items.append(
            {
                "conversation_id": str(r.id),
                "i_am_initiator": i_am_initiator,
                "counterpart": _counterpart_display(r, me),
                "initiator_revealed": r.initiator_revealed,
                "my_contact_consent": (
                    r.initiator_contact_consent if i_am_initiator else r.recipient_contact_consent
                ),
                "their_contact_consent": (
                    r.recipient_contact_consent if i_am_initiator else r.initiator_contact_consent
                ),
                "contact_exchanged": r.contact_exchanged_at is not None,
                "last_message_at": r.last_message_at.isoformat() if r.last_message_at else None,
                "last_body": r.last_body,
                "unread_count": int(r.unread_count or 0),
                "status": r.status,
            }
        )
    return items


async def messages_for(
    session: AsyncSession,
    event_id: UUID,
    conversation_id: UUID,
    me: UUID,
    *,
    initiator_id: UUID,
    initiator_alias: str,
    initiator_revealed: bool,
    counterpart_name: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(_MESSAGES, {"eid": event_id, "cid": conversation_id, "limit": limit})
    ).all()
    out = []
    for m in rows:
        mine = m.sender_id == me
        if m.kind == "system":
            display = None
        elif mine:
            display = "Tu"
        elif m.sender_id == initiator_id and not initiator_revealed:
            display = initiator_alias
        else:
            display = counterpart_name
        out.append(
            {
                "message_id": str(m.id),
                "mine": mine,
                "kind": m.kind,
                "sender_display": display,
                "body": m.body,
                "created_at": m.created_at.isoformat(),
            }
        )
    return out
