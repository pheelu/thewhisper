"""PointsService: implementazione di `PointsPort` (unica via di accredito punti).

Transazione atomica: INSERT idempotente nel ledger (ON CONFLICT DO NOTHING) e, se
inserito, UPDATE della proiezione `participant.score`. Non committa: è il chiamante
a committare e poi a pubblicare `result.events` sul realtime (persist→publish).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.gamification.infrastructure.models import PointLedgerModel
from whisper.shared.core.enums import PointReason
from whisper.shared.core.events import DomainEvent
from whisper.shared.core.ids import uuid7
from whisper.shared.core.ports import LedgerResult

_UPDATE_SCORE = text(
    "UPDATE participant SET score = score + :d, updated_at = now() "
    "WHERE id = :pid AND event_id = :eid RETURNING score"
)
_SELECT_SCORE = text("SELECT score FROM participant WHERE id = :pid AND event_id = :eid")


class PointsService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _balance(self, event_id: UUID, participant_id: UUID) -> int:
        row = (
            await self._s.execute(_SELECT_SCORE, {"pid": participant_id, "eid": event_id})
        ).scalar_one_or_none()
        return int(row) if row is not None else 0

    async def get_balance(self, *, event_id: UUID, participant_id: UUID) -> int:
        return await self._balance(event_id, participant_id)

    async def award_points(
        self,
        *,
        event_id: UUID,
        participant_id: UUID,
        delta: int,
        reason: PointReason,
        source_domain: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerResult:
        meta = metadata or {}
        stmt = (
            pg_insert(PointLedgerModel)
            .values(
                id=uuid7(),
                event_id=event_id,
                participant_id=participant_id,
                delta=delta,
                reason=reason,
                source_domain=source_domain,
                idempotency_key=idempotency_key,
                meta=meta,
            )
            .on_conflict_do_nothing(index_elements=["event_id", "idempotency_key"])
            .returning(PointLedgerModel.id)
        )
        ledger_id = (await self._s.execute(stmt)).scalar_one_or_none()

        if ledger_id is None:
            # idempotency_key già vista: no-op, nessun doppio accredito.
            return LedgerResult(
                applied=False,
                new_score=await self._balance(event_id, participant_id),
                ledger_id=None,
            )

        new_score = (
            await self._s.execute(
                _UPDATE_SCORE, {"d": delta, "pid": participant_id, "eid": event_id}
            )
        ).scalar_one()

        events = [
            DomainEvent(
                type="gamification.points_awarded",
                payload={
                    "delta": delta,
                    "new_score": new_score,
                    "reason": str(reason),
                    "source_domain": source_domain,
                    "ref": meta,
                },
                target_participant_id=participant_id,
            ),
            DomainEvent(
                type="gamification.leaderboard_updated",
                payload={"changed": [{"participant_id": str(participant_id), "score": new_score}]},
            ),
        ]
        return LedgerResult(applied=True, new_score=new_score, ledger_id=ledger_id, events=events)
