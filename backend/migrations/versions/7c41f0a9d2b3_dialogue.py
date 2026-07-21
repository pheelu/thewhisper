"""dialogue: conversation, dialogue_message, dialogue_contact

Revision ID: 7c41f0a9d2b3
Revises: 11647a2af7ce
Create Date: 2026-07-21 (scritta a mano — schema deterministico dai modelli)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c41f0a9d2b3"
down_revision: str | None = "11647a2af7ce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_origin = sa.Enum("missive", "direct", name="conversation_origin")
_status = sa.Enum("active", "closed", name="conversation_status")
_kind = sa.Enum("text", "system", name="message_kind")
_contact = sa.Enum("instagram", "phone", "other", name="dialogue_contact_type")


def upgrade() -> None:
    op.create_table(
        "conversation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("initiator_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("origin", _origin, nullable=False),
        sa.Column("status", _status, nullable=False),
        sa.Column("initiator_alias", sa.Text(), nullable=False),
        sa.Column(
            "initiator_revealed", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("revealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "initiator_contact_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "recipient_contact_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("contact_exchanged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_reply_awarded", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initiator_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recipient_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "initiator_id <> recipient_id", name=op.f("ck_conversation_distinct_parties")
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["event.id"], name=op.f("fk_conversation_event_id_event"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["initiator_id"], ["participant.id"],
            name=op.f("fk_conversation_initiator_id_participant"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"], ["participant.id"],
            name=op.f("fk_conversation_recipient_id_participant"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation")),
    )
    op.create_index(
        "uq_conversation_missive_pair",
        "conversation",
        ["event_id", "initiator_id", "recipient_id"],
        unique=True,
        postgresql_where=sa.text("origin = 'missive'"),
    )
    op.create_index("ix_conversation_initiator", "conversation", ["event_id", "initiator_id"])
    op.create_index("ix_conversation_recipient", "conversation", ["event_id", "recipient_id"])

    op.create_table(
        "dialogue_message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=True),
        sa.Column("kind", _kind, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "kind = 'system' OR char_length(body) BETWEEN 1 AND 1000",
            name=op.f("ck_dialogue_message_body_len"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["event.id"], name=op.f("fk_dialogue_message_event_id_event"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversation.id"],
            name=op.f("fk_dialogue_message_conversation_id_conversation"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"], ["participant.id"],
            name=op.f("fk_dialogue_message_sender_id_participant"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dialogue_message")),
    )
    op.create_index(
        "ix_dialogue_message_conversation", "dialogue_message", ["conversation_id", "created_at"]
    )

    op.create_table(
        "dialogue_contact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("contact_type", _contact, nullable=False),
        sa.Column("contact_value_enc", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["event.id"], name=op.f("fk_dialogue_contact_event_id_event"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversation.id"],
            name=op.f("fk_dialogue_contact_conversation_id_conversation"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"], ["participant.id"],
            name=op.f("fk_dialogue_contact_participant_id_participant"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dialogue_contact")),
    )
    op.create_index(
        "uq_dialogue_contact_owner",
        "dialogue_contact",
        ["conversation_id", "participant_id", "contact_type"],
        unique=True,
    )
    op.create_index("ix_dialogue_contact_event", "dialogue_contact", ["event_id"])


def downgrade() -> None:
    op.drop_table("dialogue_contact")
    op.drop_table("dialogue_message")
    op.drop_table("conversation")
    for enum in (_contact, _kind, _status, _origin):
        enum.drop(op.get_bind(), checkfirst=True)
