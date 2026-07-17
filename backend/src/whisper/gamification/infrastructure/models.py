"""Modelli ORM di gamification: `point_ledger` (append-only, unica fonte punti)."""

from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whisper.shared.core.enums import PointReason
from whisper.shared.infrastructure.db.base import AppendOnlyMixin, Base, UUIDMixin


class PointLedgerModel(UUIDMixin, AppendOnlyMixin, Base):
    __tablename__ = "point_ledger"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[PointReason] = mapped_column(
        Enum(PointReason, name="point_reason", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    source_domain: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Attributo python `meta` per non collidere con `Base.metadata`.
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )

    __table_args__ = (
        Index("uq_point_ledger_event_idem", "event_id", "idempotency_key", unique=True),
        Index("ix_point_ledger_event_participant", "event_id", "participant_id"),
        Index("ix_point_ledger_event_reason", "event_id", "reason"),
        CheckConstraint("delta <> 0", name="nonzero_delta"),
    )
