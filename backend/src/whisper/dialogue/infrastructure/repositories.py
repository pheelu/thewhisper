"""Implementazione SQLAlchemy del DialogueRepository (contatti cifrati a riposo)."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.dialogue.core.entities import Contact, Conversation, Message
from whisper.dialogue.core.enums import ConversationOrigin
from whisper.dialogue.infrastructure.models import (
    ConversationModel,
    DialogueContactModel,
    DialogueMessageModel,
)
from whisper.shared.infrastructure.security.secretbox import decrypt_text, encrypt_text

_IS_GUEST = text(
    "SELECT 1 FROM participant "
    "WHERE event_id = :eid AND id = :pid AND role = 'guest' AND left_at IS NULL"
)
_ALIAS_TAKEN = text(
    "SELECT 1 FROM conversation WHERE event_id = :eid AND initiator_alias = :alias LIMIT 1"
)


def _to_conversation(row: ConversationModel) -> Conversation:
    return Conversation(
        id=row.id,
        event_id=row.event_id,
        initiator_id=row.initiator_id,
        recipient_id=row.recipient_id,
        origin=row.origin,
        status=row.status,
        initiator_alias=row.initiator_alias,
        initiator_revealed=row.initiator_revealed,
        revealed_at=row.revealed_at,
        initiator_contact_consent=row.initiator_contact_consent,
        recipient_contact_consent=row.recipient_contact_consent,
        contact_exchanged_at=row.contact_exchanged_at,
        first_reply_awarded=row.first_reply_awarded,
        last_message_at=row.last_message_at,
        initiator_last_read_at=row.initiator_last_read_at,
        recipient_last_read_at=row.recipient_last_read_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyDialogueRepository:
    def __init__(self, session: AsyncSession, secret: str) -> None:
        self._s = session
        self._secret = secret

    async def add_conversation(self, conversation: Conversation) -> None:
        self._s.add(
            ConversationModel(
                id=conversation.id,
                event_id=conversation.event_id,
                initiator_id=conversation.initiator_id,
                recipient_id=conversation.recipient_id,
                origin=conversation.origin,
                status=conversation.status,
                initiator_alias=conversation.initiator_alias,
                initiator_revealed=conversation.initiator_revealed,
                revealed_at=conversation.revealed_at,
                initiator_contact_consent=conversation.initiator_contact_consent,
                recipient_contact_consent=conversation.recipient_contact_consent,
                contact_exchanged_at=conversation.contact_exchanged_at,
                first_reply_awarded=conversation.first_reply_awarded,
                last_message_at=conversation.last_message_at,
                initiator_last_read_at=conversation.initiator_last_read_at,
                recipient_last_read_at=conversation.recipient_last_read_at,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
        )
        await self._s.flush()

    async def get_conversation(self, event_id: UUID, conversation_id: UUID) -> Conversation | None:
        stmt = select(ConversationModel).where(
            ConversationModel.id == conversation_id, ConversationModel.event_id == event_id
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_conversation(row) if row else None

    async def get_conversation_for_update(
        self, event_id: UUID, conversation_id: UUID
    ) -> Conversation | None:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id, ConversationModel.event_id == event_id)
            .with_for_update()
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_conversation(row) if row else None

    async def find_missive_conversation(
        self, event_id: UUID, initiator_id: UUID, recipient_id: UUID
    ) -> Conversation | None:
        stmt = select(ConversationModel).where(
            ConversationModel.event_id == event_id,
            ConversationModel.initiator_id == initiator_id,
            ConversationModel.recipient_id == recipient_id,
            ConversationModel.origin == ConversationOrigin.missive,
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_conversation(row) if row else None

    async def update_conversation(self, conversation: Conversation) -> None:
        obj = await self._s.get(ConversationModel, conversation.id)
        if obj is None:
            return
        obj.status = conversation.status
        obj.initiator_revealed = conversation.initiator_revealed
        obj.revealed_at = conversation.revealed_at
        obj.initiator_contact_consent = conversation.initiator_contact_consent
        obj.recipient_contact_consent = conversation.recipient_contact_consent
        obj.contact_exchanged_at = conversation.contact_exchanged_at
        obj.first_reply_awarded = conversation.first_reply_awarded
        obj.last_message_at = conversation.last_message_at
        obj.initiator_last_read_at = conversation.initiator_last_read_at
        obj.recipient_last_read_at = conversation.recipient_last_read_at
        obj.updated_at = conversation.updated_at

    async def add_message(self, message: Message) -> None:
        self._s.add(
            DialogueMessageModel(
                id=message.id,
                event_id=message.event_id,
                conversation_id=message.conversation_id,
                sender_id=message.sender_id,
                kind=message.kind,
                body=message.body,
                created_at=message.created_at,
            )
        )
        await self._s.flush()

    async def participant_is_guest(self, event_id: UUID, participant_id: UUID) -> bool:
        row = (await self._s.execute(_IS_GUEST, {"eid": event_id, "pid": participant_id})).first()
        return row is not None

    async def alias_taken(self, event_id: UUID, alias: str) -> bool:
        row = (await self._s.execute(_ALIAS_TAKEN, {"eid": event_id, "alias": alias})).first()
        return row is not None

    async def upsert_contact(self, contact: Contact) -> None:
        stmt = (
            pg_insert(DialogueContactModel)
            .values(
                id=contact.id,
                event_id=contact.event_id,
                conversation_id=contact.conversation_id,
                participant_id=contact.participant_id,
                contact_type=contact.contact_type,
                contact_value_enc=encrypt_text(contact.contact_value, self._secret),
                created_at=contact.created_at,
            )
            .on_conflict_do_update(
                index_elements=["conversation_id", "participant_id", "contact_type"],
                set_={"contact_value_enc": encrypt_text(contact.contact_value, self._secret)},
            )
        )
        await self._s.execute(stmt)

    async def get_contacts(self, conversation_id: UUID) -> list[Contact]:
        stmt = select(DialogueContactModel).where(
            DialogueContactModel.conversation_id == conversation_id
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            Contact(
                id=r.id,
                event_id=r.event_id,
                conversation_id=r.conversation_id,
                participant_id=r.participant_id,
                contact_type=r.contact_type,
                contact_value=decrypt_text(r.contact_value_enc, self._secret),
                created_at=r.created_at,
            )
            for r in rows
        ]
