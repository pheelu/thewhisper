"""Modelli ORM delle scommesse: `bet_round` e `bet_stake`.

Nota di design (semplificazione documentata rispetto all'architettura §2.6): le
opzioni sono i partecipanti stessi — la puntata riferisce direttamente il
candidato (`candidate_participant_id`) e i pool per-candidato sono aggregazioni.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from whisper.betting.core.enums import BetRoundStatus, BetStakeStatus
from whisper.shared.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


class BetRoundModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bet_round"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    # Snapshot immutabile del template
    template_code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_rule: Mapped[str] = mapped_column(Text, nullable=False)
    min_stake: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_stake: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    status: Mapped[BetRoundStatus] = mapped_column(
        _enum(BetRoundStatus, "bet_round_status"),
        nullable=False,
        default=BetRoundStatus.open,
    )
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    measurement_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_pool: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    winning_candidate_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PGUUID(as_uuid=True)))
    void_reason: Mapped[str | None] = mapped_column(Text)
    settlement_idempotency_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("uq_bet_round_settlement_key", "settlement_idempotency_key", unique=True),
        # Un solo round attivo per evento
        Index(
            "uq_bet_round_one_active",
            "event_id",
            unique=True,
            postgresql_where=text("status IN ('scheduled','open','locked')"),
        ),
        Index("ix_bet_round_event_status", "event_id", "status"),
        CheckConstraint("closes_at > opens_at", name="betting_window"),
        CheckConstraint("measurement_end >= closes_at", name="measurement_after_close"),
        CheckConstraint("max_stake >= min_stake", name="stake_bounds"),
    )


class BetStakeModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bet_stake"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    round_id: Mapped[UUID] = mapped_column(
        ForeignKey("bet_round.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    candidate_participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[BetStakeStatus] = mapped_column(
        _enum(BetStakeStatus, "bet_stake_status"),
        nullable=False,
        default=BetStakeStatus.placed,
    )
    payout: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        # Una puntata attiva per giocatore per round
        Index(
            "uq_bet_stake_round_participant",
            "round_id",
            "participant_id",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
        ),
        Index("ix_bet_stake_round", "round_id"),
        Index("ix_bet_stake_participant", "event_id", "participant_id"),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("payout >= 0", name="positive_payout"),
    )
