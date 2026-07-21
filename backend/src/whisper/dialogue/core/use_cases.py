"""Use case del dialogo: missive segrete, chat, rivelazione, scambio contatti.

Regole (dal documento di architettura):
- La missiva apre una conversazione con il mittente MASCHERATO da un alias.
- `missive_replied` +10 al mittente alla PRIMA risposta del destinatario (1×conv).
- Il reveal del mittente è monotono (irreversibile) e produce un messaggio di sistema.
- Lo scambio contatti richiede doppio consenso + mittente rivelato; +15 a testa
  (`dialogue_matched`). I contatti reali restano SOLO nel dominio dialogue.
"""

from dataclasses import dataclass, field
from uuid import UUID

from whisper.dialogue.core.entities import Contact, Conversation, Message
from whisper.dialogue.core.enums import (
    ContactType,
    ConversationOrigin,
    ConversationStatus,
    MessageKind,
)
from whisper.dialogue.core.repositories import DialogueRepository
from whisper.dialogue.core.services import random_alias
from whisper.shared.core.clock import Clock
from whisper.shared.core.enums import PointReason
from whisper.shared.core.errors import ForbiddenError, NotFoundError, ValidationError
from whisper.shared.core.events import DomainEvent
from whisper.shared.core.ids import uuid7
from whisper.shared.core.ports import PointsPort

MISSIVE_REPLIED_POINTS = 10
DIALOGUE_MATCHED_POINTS = 15
_ALIAS_ATTEMPTS = 10


@dataclass
class DialogueResult:
    conversation: Conversation
    message: Message | None = None
    events: list[DomainEvent] = field(default_factory=list)


def _display_name_for(conversation: Conversation, *, viewer_is_recipient: bool) -> str | None:
    """Nome del mittente visto dal destinatario: alias finché non rivelato.

    Ritorna None quando serve lo pseudonimo reale (lo risolve l'adapter).
    """
    if viewer_is_recipient and not conversation.initiator_revealed:
        return conversation.initiator_alias
    return None


async def _fresh_alias(repo: DialogueRepository, event_id: UUID) -> str:
    for _ in range(_ALIAS_ATTEMPTS):
        alias = random_alias()
        if not await repo.alias_taken(event_id, alias):
            return alias
    return random_alias()  # collisione improbabilissima: accetta comunque


async def send_missive(
    repo: DialogueRepository,
    clock: Clock,
    *,
    event_id: UUID,
    sender_id: UUID,
    recipient_id: UUID,
    body: str,
) -> DialogueResult:
    if sender_id == recipient_id:
        raise ValidationError("Non puoi scriverti da solo.", code="dialogue.self_missive")
    if not await repo.participant_is_guest(event_id, recipient_id):
        raise NotFoundError("Destinatario non trovato.", code="dialogue.recipient_not_found")

    now = clock.now()
    conversation = await repo.find_missive_conversation(event_id, sender_id, recipient_id)
    created = conversation is None
    if conversation is None:
        conversation = Conversation(
            id=uuid7(),
            event_id=event_id,
            initiator_id=sender_id,
            recipient_id=recipient_id,
            origin=ConversationOrigin.missive,
            status=ConversationStatus.active,
            initiator_alias=await _fresh_alias(repo, event_id),
            initiator_revealed=False,
            revealed_at=None,
            initiator_contact_consent=False,
            recipient_contact_consent=False,
            contact_exchanged_at=None,
            first_reply_awarded=False,
            last_message_at=None,
            initiator_last_read_at=None,
            recipient_last_read_at=None,
            created_at=now,
            updated_at=now,
        )
        await repo.add_conversation(conversation)

    message = Message(
        id=uuid7(),
        event_id=event_id,
        conversation_id=conversation.id,
        sender_id=sender_id,
        kind=MessageKind.text,
        body=body,
        created_at=now,
    )
    await repo.add_message(message)
    conversation.last_message_at = now
    conversation.initiator_last_read_at = now
    conversation.updated_at = now
    await repo.update_conversation(conversation)

    events = [
        DomainEvent(
            type="dialogue.missive_received",
            payload={
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "sender_display": conversation.initiator_alias,
                "preview": body[:80],
                "origin": "missive",
                "new_conversation": created,
            },
            target_participant_id=recipient_id,
        )
    ]
    return DialogueResult(conversation=conversation, message=message, events=events)


async def _load_for(
    repo: DialogueRepository, event_id: UUID, conversation_id: UUID, participant_id: UUID
) -> Conversation:
    conversation = await repo.get_conversation(event_id, conversation_id)
    if conversation is None or conversation.side_of(participant_id) is None:
        raise NotFoundError("Conversazione non trovata.", code="dialogue.not_found")
    return conversation


async def send_message(
    repo: DialogueRepository,
    points: PointsPort,
    clock: Clock,
    *,
    event_id: UUID,
    conversation_id: UUID,
    sender_id: UUID,
    body: str,
) -> DialogueResult:
    conversation = await _load_for(repo, event_id, conversation_id, sender_id)
    if conversation.status != ConversationStatus.active:
        raise ForbiddenError("La conversazione è chiusa.", code="dialogue.closed")

    now = clock.now()
    message = Message(
        id=uuid7(),
        event_id=event_id,
        conversation_id=conversation.id,
        sender_id=sender_id,
        kind=MessageKind.text,
        body=body,
        created_at=now,
    )
    await repo.add_message(message)
    conversation.last_message_at = now
    if sender_id == conversation.initiator_id:
        conversation.initiator_last_read_at = now
    else:
        conversation.recipient_last_read_at = now
    conversation.updated_at = now

    events: list[DomainEvent] = []

    # Prima risposta del destinatario → la missiva "ha generato risposta": +10 al mittente.
    if sender_id == conversation.recipient_id and not conversation.first_reply_awarded:
        conversation.first_reply_awarded = True
        result = await points.award_points(
            event_id=event_id,
            participant_id=conversation.initiator_id,
            delta=MISSIVE_REPLIED_POINTS,
            reason=PointReason.missive_replied,
            source_domain="dialogue",
            idempotency_key=f"missive_replied:{conversation.id}",
            metadata={"conversation_id": str(conversation.id)},
        )
        events.extend(result.events)

    await repo.update_conversation(conversation)

    # Il mittente del messaggio è mascherato solo se è l'iniziatore non rivelato.
    sender_display = (
        conversation.initiator_alias
        if sender_id == conversation.initiator_id and not conversation.initiator_revealed
        else None  # l'adapter risolve lo pseudonimo reale
    )
    events.append(
        DomainEvent(
            type="dialogue.message_received",
            payload={
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "sender_display": sender_display,
                "sender_id_if_open": None if sender_display else str(sender_id),
                "kind": "text",
                "body": body,
                "ts": now.isoformat(),
            },
            target_participant_id=conversation.counterpart_of(sender_id),
        )
    )
    return DialogueResult(conversation=conversation, message=message, events=events)


async def reveal_identity(
    repo: DialogueRepository,
    clock: Clock,
    *,
    event_id: UUID,
    conversation_id: UUID,
    participant_id: UUID,
) -> DialogueResult:
    conversation = await _load_for(repo, event_id, conversation_id, participant_id)
    if participant_id != conversation.initiator_id:
        raise ForbiddenError(
            "Solo chi ha scritto la missiva può rivelarsi.", code="dialogue.not_initiator"
        )
    if conversation.initiator_revealed:
        return DialogueResult(conversation=conversation)

    now = clock.now()
    conversation.initiator_revealed = True
    conversation.revealed_at = now
    conversation.updated_at = now
    await repo.update_conversation(conversation)

    system = Message(
        id=uuid7(),
        event_id=event_id,
        conversation_id=conversation.id,
        sender_id=None,
        kind=MessageKind.system,
        body="identity_revealed",
        created_at=now,
    )
    await repo.add_message(system)

    events = [
        DomainEvent(
            type="dialogue.revealed",
            payload={
                "conversation_id": str(conversation.id),
                "participant_id": str(participant_id),
            },
            target_participant_id=conversation.recipient_id,
        )
    ]
    return DialogueResult(conversation=conversation, message=system, events=events)


async def set_contact(
    repo: DialogueRepository,
    points: PointsPort,
    clock: Clock,
    *,
    event_id: UUID,
    conversation_id: UUID,
    participant_id: UUID,
    contact_type: ContactType,
    contact_value: str,
) -> DialogueResult:
    """Registra il proprio contatto e il consenso allo scambio.

    Quando entrambe le parti hanno acconsentito e il mittente si è rivelato, lo
    scambio avviene: messaggio di sistema + evento mirato a entrambi + punti.
    """
    conversation = await _load_for(repo, event_id, conversation_id, participant_id)
    now = clock.now()

    await repo.upsert_contact(
        Contact(
            id=uuid7(),
            event_id=event_id,
            conversation_id=conversation.id,
            participant_id=participant_id,
            contact_type=contact_type,
            contact_value=contact_value,
            created_at=now,
        )
    )
    if participant_id == conversation.initiator_id:
        conversation.initiator_contact_consent = True
    else:
        conversation.recipient_contact_consent = True
    conversation.updated_at = now

    events: list[DomainEvent] = []
    exchanged = False

    if conversation.contact_exchange_ready:
        conversation.contact_exchanged_at = now
        exchanged = True
        await repo.add_message(
            Message(
                id=uuid7(),
                event_id=event_id,
                conversation_id=conversation.id,
                sender_id=None,
                kind=MessageKind.system,
                body="contact_exchanged",
                created_at=now,
            )
        )
        for pid in (conversation.initiator_id, conversation.recipient_id):
            result = await points.award_points(
                event_id=event_id,
                participant_id=pid,
                delta=DIALOGUE_MATCHED_POINTS,
                reason=PointReason.dialogue_matched,
                source_domain="dialogue",
                idempotency_key=f"dialogue_matched:{conversation.id}:{pid}",
                metadata={"conversation_id": str(conversation.id)},
            )
            events.extend(result.events)
            events.append(
                DomainEvent(
                    type="dialogue.contact_exchanged",
                    payload={"conversation_id": str(conversation.id)},
                    target_participant_id=pid,
                )
            )
    else:
        events.append(
            DomainEvent(
                type="dialogue.contact_consent_updated",
                payload={
                    "conversation_id": str(conversation.id),
                    "consented": True,
                    "pending": not exchanged,
                },
                target_participant_id=conversation.counterpart_of(participant_id),
            )
        )

    await repo.update_conversation(conversation)
    return DialogueResult(conversation=conversation, events=events)


async def mark_read(
    repo: DialogueRepository,
    clock: Clock,
    *,
    event_id: UUID,
    conversation_id: UUID,
    participant_id: UUID,
) -> Conversation:
    conversation = await _load_for(repo, event_id, conversation_id, participant_id)
    now = clock.now()
    if participant_id == conversation.initiator_id:
        conversation.initiator_last_read_at = now
    else:
        conversation.recipient_last_read_at = now
    conversation.updated_at = now
    await repo.update_conversation(conversation)
    return conversation
