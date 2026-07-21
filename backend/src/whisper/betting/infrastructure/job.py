"""Job dello scheduler: fa avanzare le scommesse di tutti gli eventi aperti.

Registrato nel loop unico (`shared/scheduler`) con cadenza 60s. Idempotente:
le transizioni e i payout usano chiavi idempotenti sul ledger.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import text

from whisper.betting.infrastructure.service import BettingService
from whisper.shared.infrastructure.db.session import SessionFactory
from whisper.shared.infrastructure.realtime.broker import EventBus, RealtimeMessage

logger = logging.getLogger("whisper.betting")

_OPEN_EVENTS = text("SELECT id FROM event WHERE status = 'open'")


def make_betting_tick(bus: EventBus):
    async def betting_tick() -> None:
        now = datetime.now(UTC)
        async with SessionFactory() as session:
            event_ids = [r.id for r in (await session.execute(_OPEN_EVENTS)).all()]
            for event_id in event_ids:
                try:
                    events = await BettingService(session).tick(event_id, now)
                    await session.commit()
                    for e in events:
                        await bus.publish(
                            RealtimeMessage(
                                event_id=event_id,
                                type=e.type,
                                payload=e.payload,
                                target_participant_id=e.target_participant_id,
                            )
                        )
                except Exception:  # noqa: BLE001 — un evento non blocca gli altri
                    logger.exception("betting tick fallito per evento %s", event_id)
                    await session.rollback()

    return betting_tick
