"""Porte condivise (Protocol) per la collaborazione cross-dominio.

I domini collaborano tramite queste porte, mai importando i `models.py` altrui.
`PointsPort` è implementata SOLO da `gamification` (owner del ledger); gli altri
domini accreditano punti attraverso di essa in modo idempotente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from whisper.shared.core.enums import PointReason
from whisper.shared.core.events import DomainEvent


@dataclass(frozen=True)
class LedgerResult:
    """Esito di un accredito punti.

    `events` sono i `DomainEvent` realtime da pubblicare DOPO il commit (vuoto se
    l'accredito è stato un no-op idempotente).
    """

    applied: bool  # False se idempotency_key già vista (no-op)
    new_score: int
    ledger_id: UUID | None
    events: list[DomainEvent] = field(default_factory=list)


class PointsPort(Protocol):
    """Unica via di accredito punti. Implementata da `gamification`."""

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
    ) -> LedgerResult: ...

    async def get_balance(self, *, event_id: UUID, participant_id: UUID) -> int: ...


class ErasablePort(Protocol):
    """Ogni dominio implementa la cancellazione GDPR dei propri dati per partecipante."""

    async def erase_participant(self, *, event_id: UUID, participant_id: UUID) -> None: ...
