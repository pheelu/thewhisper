"""Router HTTP del dialogo: /missives e /conversations."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.dialogue.core import use_cases
from whisper.dialogue.infrastructure import queries
from whisper.dialogue.infrastructure.repositories import SqlAlchemyDialogueRepository
from whisper.dialogue.infrastructure.schemas import (
    ContactRequest,
    SendMessageRequest,
    SendMissiveRequest,
)
from whisper.gamification.infrastructure.points_service import PointsService
from whisper.shared.core.clock import SystemClock
from whisper.shared.core.errors import ForbiddenError, NotFoundError
from whisper.shared.core.events import DomainEvent
from whisper.shared.infrastructure.http.deps import (
    AppSettings,
    Bus,
    CurrentParticipant,
    DbSession,
)
from whisper.shared.infrastructure.realtime.broker import EventBus, RealtimeMessage

router = APIRouter(prefix="/api/v1", tags=["dialogue"])
_clock = SystemClock()

_PSEUDONYM = sql_text("SELECT pseudonym FROM participant WHERE id = :pid")


def _repo(db: AsyncSession, settings) -> SqlAlchemyDialogueRepository:
    return SqlAlchemyDialogueRepository(db, settings.secret_key)


async def _resolve_open_sender(db: AsyncSession, events: list[DomainEvent]) -> list[DomainEvent]:
    """Sostituisce `sender_id_if_open` con lo pseudonimo reale (mittente non mascherato)."""
    out: list[DomainEvent] = []
    for e in events:
        if e.type == "dialogue.message_received" and e.payload.get("sender_display") is None:
            pid = e.payload.get("sender_id_if_open")
            name = (await db.execute(_PSEUDONYM, {"pid": pid})).scalar_one_or_none() if pid else None
            payload = {k: v for k, v in e.payload.items() if k != "sender_id_if_open"}
            payload["sender_display"] = name or "Sconosciuto"
            out.append(
                DomainEvent(type=e.type, payload=payload, target_participant_id=e.target_participant_id)
            )
        else:
            out.append(e)
    return out


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


@router.post("/missives", status_code=status.HTTP_201_CREATED)
async def send_missive(
    body: SendMissiveRequest,
    db: DbSession,
    context: CurrentParticipant,
    bus: Bus,
    settings: AppSettings,
) -> dict[str, Any]:
    result = await use_cases.send_missive(
        _repo(db, settings),
        _clock,
        event_id=context.event_id,
        sender_id=context.participant_id,
        recipient_id=body.recipient_participant_id,
        body=body.body,
    )
    await db.commit()
    await _publish(bus, context.event_id, result.events)
    return {
        "conversation_id": str(result.conversation.id),
        "your_alias": result.conversation.initiator_alias,
    }


@router.get("/conversations")
async def list_conversations(db: DbSession, context: CurrentParticipant) -> dict[str, Any]:
    items = await queries.conversations_for(db, context.event_id, context.participant_id)
    return {"items": items}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID, db: DbSession, context: CurrentParticipant, settings: AppSettings
) -> dict[str, Any]:
    repo = _repo(db, settings)
    conversation = await repo.get_conversation(context.event_id, conversation_id)
    if conversation is None or conversation.side_of(context.participant_id) is None:
        raise NotFoundError("Conversazione non trovata.", code="dialogue.not_found")

    me = context.participant_id
    i_am_initiator = me == conversation.initiator_id
    counterpart_id = conversation.counterpart_of(me)
    counterpart_name = (
        await db.execute(_PSEUDONYM, {"pid": counterpart_id})
    ).scalar_one_or_none() or "Sconosciuto"

    # mascheramento: se io sono il destinatario e il mittente non si è rivelato
    counterpart_display = (
        conversation.initiator_alias
        if (not i_am_initiator and not conversation.initiator_revealed)
        else counterpart_name
    )

    messages = await queries.messages_for(
        db,
        context.event_id,
        conversation_id,
        me,
        initiator_id=conversation.initiator_id,
        initiator_alias=conversation.initiator_alias,
        initiator_revealed=conversation.initiator_revealed,
        counterpart_name=counterpart_name,
    )

    contacts = None
    if conversation.contact_exchanged_at is not None:
        contacts = [
            {
                "participant_id": str(c.participant_id),
                "contact_type": str(c.contact_type),
                "contact_value": c.contact_value,
                "mine": c.participant_id == me,
            }
            for c in await repo.get_contacts(conversation_id)
        ]

    my_consent = (
        conversation.initiator_contact_consent
        if i_am_initiator
        else conversation.recipient_contact_consent
    )
    their_consent = (
        conversation.recipient_contact_consent
        if i_am_initiator
        else conversation.initiator_contact_consent
    )

    return {
        "conversation_id": str(conversation.id),
        "i_am_initiator": i_am_initiator,
        "my_alias": conversation.initiator_alias if i_am_initiator else None,
        "i_am_revealed": conversation.initiator_revealed if i_am_initiator else True,
        "counterpart_display": counterpart_display,
        "counterpart_masked": not i_am_initiator and not conversation.initiator_revealed,
        "initiator_revealed": conversation.initiator_revealed,
        "my_contact_consent": my_consent,
        "their_contact_consent": their_consent,
        "contact_exchanged": conversation.contact_exchanged_at is not None,
        "contacts": contacts,
        "status": str(conversation.status),
        "messages": messages,
    }


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    db: DbSession,
    context: CurrentParticipant,
    bus: Bus,
    settings: AppSettings,
) -> dict[str, Any]:
    result = await use_cases.send_message(
        _repo(db, settings),
        PointsService(db),
        _clock,
        event_id=context.event_id,
        conversation_id=conversation_id,
        sender_id=context.participant_id,
        body=body.body,
    )
    events = await _resolve_open_sender(db, result.events)
    await db.commit()
    await _publish(bus, context.event_id, events)
    assert result.message is not None
    return {
        "message_id": str(result.message.id),
        "created_at": result.message.created_at.isoformat(),
    }


@router.post("/conversations/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    conversation_id: UUID, db: DbSession, context: CurrentParticipant, settings: AppSettings
):
    await use_cases.mark_read(
        _repo(db, settings),
        _clock,
        event_id=context.event_id,
        conversation_id=conversation_id,
        participant_id=context.participant_id,
    )
    await db.commit()


@router.post("/conversations/{conversation_id}/reveal")
async def reveal(
    conversation_id: UUID,
    db: DbSession,
    context: CurrentParticipant,
    bus: Bus,
    settings: AppSettings,
) -> dict[str, Any]:
    result = await use_cases.reveal_identity(
        _repo(db, settings),
        _clock,
        event_id=context.event_id,
        conversation_id=conversation_id,
        participant_id=context.participant_id,
    )
    # arricchisci con lo pseudonimo reale per il destinatario
    enriched: list[DomainEvent] = []
    for e in result.events:
        if e.type == "dialogue.revealed":
            name = (
                await db.execute(_PSEUDONYM, {"pid": context.participant_id})
            ).scalar_one_or_none()
            enriched.append(
                DomainEvent(
                    type=e.type,
                    payload={**e.payload, "pseudonym": name},
                    target_participant_id=e.target_participant_id,
                )
            )
        else:
            enriched.append(e)
    await db.commit()
    await _publish(bus, context.event_id, enriched)
    return {"revealed": True}


@router.post("/conversations/{conversation_id}/contact")
async def set_contact(
    conversation_id: UUID,
    body: ContactRequest,
    db: DbSession,
    context: CurrentParticipant,
    bus: Bus,
    settings: AppSettings,
) -> dict[str, Any]:
    result = await use_cases.set_contact(
        _repo(db, settings),
        PointsService(db),
        _clock,
        event_id=context.event_id,
        conversation_id=conversation_id,
        participant_id=context.participant_id,
        contact_type=body.contact_type,
        contact_value=body.contact_value,
    )
    await db.commit()
    await _publish(bus, context.event_id, result.events)
    return {
        "contact_exchanged": result.conversation.contact_exchanged_at is not None,
    }
