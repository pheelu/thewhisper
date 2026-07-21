"""Servizio delle scommesse: ciclo di vita del round, puntate, settlement.

Le regole pure (payout parimutuel, template) vivono in `betting/core`; qui c'è
l'orchestrazione con DB e ledger punti. L'escrow e i payout passano SOLO da
`PointsService` con chiavi idempotenti (`bet_staked/bet_won/bet_refunded:{stake_id}`).
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.betting.core.enums import BetRoundStatus, BetStakeStatus
from whisper.betting.core.services import StakeView, parimutuel_payouts
from whisper.betting.core.templates import BetTemplate, template_by_index
from whisper.betting.infrastructure.models import BetRoundModel, BetStakeModel
from whisper.gamification.infrastructure.points_service import PointsService
from whisper.shared.core.enums import PointReason
from whisper.shared.core.errors import ConflictError, NotFoundError, ValidationError
from whisper.shared.core.events import DomainEvent
from whisper.shared.core.ids import uuid7

_ROUND_COUNT = text("SELECT count(*) FROM bet_round WHERE event_id = :eid")
_IS_GUEST = text(
    "SELECT 1 FROM participant WHERE event_id = :eid AND id = :pid "
    "AND role = 'guest' AND left_at IS NULL"
)

# Metriche di risoluzione: attività nella finestra [closes_at, measurement_end)
_METRIC_SQL = {
    "most_photographed": text(
        """
        SELECT subject_participant_id AS pid, count(*) AS score FROM photo
        WHERE event_id = :eid AND status = 'published'
          AND published_at >= :start AND published_at < :end
        GROUP BY 1 ORDER BY 2 DESC
        """
    ),
    "top_gossip": text(
        """
        SELECT author_participant_id AS pid, count(*) AS score FROM whisper_comment
        WHERE event_id = :eid AND status = 'visible'
          AND created_at >= :start AND created_at < :end
          AND author_participant_id IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
        """
    ),
    "best_detective": text(
        """
        SELECT guesser_participant_id AS pid, count(*) AS score FROM whisper_guess
        WHERE event_id = :eid AND is_correct
          AND created_at >= :start AND created_at < :end
        GROUP BY 1 ORDER BY 2 DESC
        """
    ),
}


class BettingService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session
        self._points = PointsService(session)

    # ---------- round ----------
    async def get_active_round(self, event_id: UUID) -> BetRoundModel | None:
        stmt = select(BetRoundModel).where(
            BetRoundModel.event_id == event_id,
            BetRoundModel.status.in_(
                [BetRoundStatus.scheduled, BetRoundStatus.open, BetRoundStatus.locked]
            ),
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def create_round(
        self, event_id: UUID, now: datetime, template: BetTemplate | None = None
    ) -> tuple[BetRoundModel, list[DomainEvent]]:
        if await self.get_active_round(event_id) is not None:
            raise ConflictError("C'è già una scommessa in corso.", code="betting.round_active")

        if template is None:
            count = (await self._s.execute(_ROUND_COUNT, {"eid": event_id})).scalar_one()
            template = template_by_index(int(count))

        round_ = BetRoundModel(
            id=uuid7(),
            event_id=event_id,
            template_code=template.code,
            title=template.title,
            prompt=template.prompt,
            resolution_rule=template.resolution_rule,
            min_stake=template.min_stake,
            max_stake=template.max_stake,
            status=BetRoundStatus.open,
            opens_at=now,
            closes_at=now + timedelta(seconds=template.betting_seconds),
            measurement_end=now
            + timedelta(seconds=template.betting_seconds + template.measurement_seconds),
        )
        self._s.add(round_)
        await self._s.flush()
        events = [
            DomainEvent(
                type="betting.round_opened",
                payload=self._round_payload(round_),
            )
        ]
        return round_, events

    def _round_payload(self, r: BetRoundModel) -> dict:
        return {
            "round_id": str(r.id),
            "title": r.title,
            "prompt": r.prompt,
            "status": str(r.status),
            "opens_at": r.opens_at.isoformat(),
            "closes_at": r.closes_at.isoformat(),
            "measurement_end": r.measurement_end.isoformat(),
            "total_pool": r.total_pool,
            "min_stake": r.min_stake,
            "max_stake": r.max_stake,
        }

    async def _get_round(self, event_id: UUID, round_id: UUID) -> BetRoundModel:
        stmt = select(BetRoundModel).where(
            BetRoundModel.id == round_id, BetRoundModel.event_id == event_id
        )
        round_ = (await self._s.execute(stmt)).scalar_one_or_none()
        if round_ is None:
            raise NotFoundError("Scommessa non trovata.", code="betting.round_not_found")
        return round_

    # ---------- puntate ----------
    async def place_stake(
        self,
        *,
        event_id: UUID,
        round_id: UUID,
        participant_id: UUID,
        candidate_id: UUID,
        amount: int,
        now: datetime,
    ) -> tuple[BetStakeModel, list[DomainEvent]]:
        round_ = await self._get_round(event_id, round_id)
        if round_.status != BetRoundStatus.open or now >= round_.closes_at:
            raise ConflictError("Le puntate sono chiuse.", code="betting.closed")
        if not (round_.min_stake <= amount <= round_.max_stake):
            raise ValidationError(
                f"La puntata deve essere tra {round_.min_stake} e {round_.max_stake} punti.",
                code="betting.bad_amount",
            )
        if candidate_id == participant_id:
            raise ValidationError("Non puoi puntare su te stesso.", code="betting.self_bet")
        if (await self._s.execute(_IS_GUEST, {"eid": event_id, "pid": candidate_id})).first() is None:
            raise ValidationError("Candidato non valido.", code="betting.bad_candidate")

        existing = (
            await self._s.execute(
                select(BetStakeModel).where(
                    BetStakeModel.round_id == round_id,
                    BetStakeModel.participant_id == participant_id,
                    BetStakeModel.status != BetStakeStatus.cancelled,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Hai già puntato in questo round.", code="betting.already_staked")

        balance = await self._points.get_balance(event_id=event_id, participant_id=participant_id)
        if amount > balance:
            raise ConflictError("Punti insufficienti.", code="betting.insufficient_points")

        stake = BetStakeModel(
            id=uuid7(),
            event_id=event_id,
            round_id=round_id,
            participant_id=participant_id,
            candidate_participant_id=candidate_id,
            amount=amount,
            status=BetStakeStatus.placed,
        )
        self._s.add(stake)
        await self._s.flush()

        # escrow: −amount dal saldo, idempotente sulla puntata
        result = await self._points.award_points(
            event_id=event_id,
            participant_id=participant_id,
            delta=-amount,
            reason=PointReason.bet_staked,
            source_domain="betting",
            idempotency_key=f"bet_staked:{stake.id}",
            metadata={"round_id": str(round_id)},
        )
        round_.total_pool += amount

        events = [
            *result.events,
            DomainEvent(
                type="betting.stake_confirmed",
                payload={
                    "round_id": str(round_id),
                    "stake_id": str(stake.id),
                    "candidate_participant_id": str(candidate_id),
                    "amount": amount,
                    "new_score": result.new_score,
                },
                target_participant_id=participant_id,
            ),
            DomainEvent(
                type="betting.pool_updated",
                payload={"round_id": str(round_id), "total_pool": round_.total_pool},
            ),
        ]
        return stake, events

    async def cancel_stake(
        self, *, event_id: UUID, stake_id: UUID, participant_id: UUID, now: datetime
    ) -> list[DomainEvent]:
        stake = (
            await self._s.execute(
                select(BetStakeModel).where(
                    BetStakeModel.id == stake_id, BetStakeModel.event_id == event_id
                )
            )
        ).scalar_one_or_none()
        if stake is None or stake.participant_id != participant_id:
            raise NotFoundError("Puntata non trovata.", code="betting.stake_not_found")
        if stake.status != BetStakeStatus.placed:
            raise ConflictError("Puntata non annullabile.", code="betting.not_cancellable")
        round_ = await self._get_round(event_id, stake.round_id)
        if round_.status != BetRoundStatus.open or now >= round_.closes_at:
            raise ConflictError("Le puntate sono chiuse.", code="betting.closed")

        stake.status = BetStakeStatus.cancelled
        round_.total_pool -= stake.amount
        result = await self._points.award_points(
            event_id=event_id,
            participant_id=participant_id,
            delta=stake.amount,
            reason=PointReason.bet_refunded,
            source_domain="betting",
            idempotency_key=f"bet_refunded:{stake.id}",
            metadata={"round_id": str(stake.round_id), "cancelled": True},
        )
        return [
            *result.events,
            DomainEvent(
                type="betting.pool_updated",
                payload={"round_id": str(round_.id), "total_pool": round_.total_pool},
            ),
        ]

    # ---------- transizioni ----------
    async def lock_round(self, round_: BetRoundModel, now: datetime) -> list[DomainEvent]:
        if round_.status != BetRoundStatus.open:
            return []
        round_.status = BetRoundStatus.locked
        round_.closes_at = min(round_.closes_at, now)
        return [
            DomainEvent(
                type="betting.round_locked",
                payload={"round_id": str(round_.id), "total_pool": round_.total_pool},
            )
        ]

    async def settle_round(self, round_: BetRoundModel, now: datetime) -> list[DomainEvent]:
        """Risolve il round: calcola la metrica, i vincitori e i payout. Idempotente."""
        if round_.status not in (BetRoundStatus.open, BetRoundStatus.locked):
            return []
        # idempotenza: chiave unica per round
        round_.settlement_idempotency_key = f"bet_settle:{round_.id}"

        stakes = (
            (
                await self._s.execute(
                    select(BetStakeModel)
                    .where(
                        BetStakeModel.round_id == round_.id,
                        BetStakeModel.status == BetStakeStatus.placed,
                    )
                    .order_by(BetStakeModel.created_at.asc(), BetStakeModel.id.asc())
                )
            )
            .scalars()
            .all()
        )

        window_end = min(round_.measurement_end, now)
        metric_rows = (
            await self._s.execute(
                _METRIC_SQL[round_.resolution_rule],
                {"eid": round_.event_id, "start": round_.closes_at, "end": window_end},
            )
        ).all()

        events: list[DomainEvent] = []
        top_score = metric_rows[0].score if metric_rows else 0

        if not stakes or top_score == 0:
            # nessuna puntata o nessuna attività misurabile → void + rimborso totale
            round_.status = BetRoundStatus.void
            round_.void_reason = "no_stakes" if not stakes else "no_activity"
            round_.settled_at = now
            for stake in stakes:
                stake.status = BetStakeStatus.refunded
                stake.payout = stake.amount
                result = await self._points.award_points(
                    event_id=round_.event_id,
                    participant_id=stake.participant_id,
                    delta=stake.amount,
                    reason=PointReason.bet_refunded,
                    source_domain="betting",
                    idempotency_key=f"bet_refunded:{stake.id}",
                    metadata={"round_id": str(round_.id), "void": True},
                )
                events.extend(result.events)
            events.append(
                DomainEvent(
                    type="betting.round_voided",
                    payload={"round_id": str(round_.id), "reason": round_.void_reason},
                )
            )
            return events

        winning = {row.pid for row in metric_rows if row.score == top_score}
        round_.winning_candidate_ids = sorted(winning, key=str)

        views = [
            StakeView(
                stake_id=s.id,
                participant_id=s.participant_id,
                candidate_id=s.candidate_participant_id,
                amount=s.amount,
                placed_order=i,
            )
            for i, s in enumerate(stakes)
        ]
        payouts = parimutuel_payouts(views, winning)

        if payouts is None:
            # nessuno ha puntato sul vincitore → rimborso totale
            round_.status = BetRoundStatus.void
            round_.void_reason = "no_winning_stakes"
            round_.settled_at = now
            for stake in stakes:
                stake.status = BetStakeStatus.refunded
                stake.payout = stake.amount
                result = await self._points.award_points(
                    event_id=round_.event_id,
                    participant_id=stake.participant_id,
                    delta=stake.amount,
                    reason=PointReason.bet_refunded,
                    source_domain="betting",
                    idempotency_key=f"bet_refunded:{stake.id}",
                    metadata={"round_id": str(round_.id), "void": True},
                )
                events.extend(result.events)
            events.append(
                DomainEvent(
                    type="betting.round_voided",
                    payload={"round_id": str(round_.id), "reason": round_.void_reason},
                )
            )
            return events

        by_stake = {p.stake_id: p for p in payouts}
        round_.status = BetRoundStatus.settled
        round_.settled_at = now
        for stake in stakes:
            payout = by_stake.get(stake.id)
            if payout is not None:
                stake.status = BetStakeStatus.won
                stake.payout = payout.amount
                result = await self._points.award_points(
                    event_id=round_.event_id,
                    participant_id=stake.participant_id,
                    delta=payout.amount,
                    reason=PointReason.bet_won,
                    source_domain="betting",
                    idempotency_key=f"bet_won:{stake.id}",
                    metadata={"round_id": str(round_.id)},
                )
                events.extend(result.events)
                events.append(
                    DomainEvent(
                        type="betting.payout_received",
                        payload={
                            "round_id": str(round_.id),
                            "stake_id": str(stake.id),
                            "payout": payout.amount,
                            "profit": payout.amount - stake.amount,
                            "new_score": result.new_score,
                        },
                        target_participant_id=stake.participant_id,
                    )
                )
            else:
                stake.status = BetStakeStatus.lost

        events.append(
            DomainEvent(
                type="betting.round_settled",
                payload={
                    "round_id": str(round_.id),
                    "winning_candidate_ids": [str(w) for w in (round_.winning_candidate_ids or [])],
                    "total_pool": round_.total_pool,
                },
            )
        )
        return events

    async def tick(self, event_id: UUID, now: datetime) -> list[DomainEvent]:
        """Avanza il round attivo (o ne crea uno) in base all'orologio. Idempotente."""
        round_ = await self.get_active_round(event_id)
        if round_ is None:
            _, events = await self.create_round(event_id, now)
            return events
        if round_.status == BetRoundStatus.open and now >= round_.closes_at:
            events = await self.lock_round(round_, now)
            if now >= round_.measurement_end:
                events.extend(await self.settle_round(round_, now))
            return events
        if round_.status == BetRoundStatus.locked and now >= round_.measurement_end:
            return await self.settle_round(round_, now)
        return []
