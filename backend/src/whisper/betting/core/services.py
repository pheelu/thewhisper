"""Regole pure delle scommesse: payout parimutuel.

Formula (dal documento di architettura, rake=0):
  payout_i = floor(amount_i * total_pool / winning_pool)
Il resto (total_pool - somma payout) va alla prima puntata vincente per
conservare i punti. Nessun vincitore → void con rimborso totale.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StakeView:
    stake_id: UUID
    participant_id: UUID
    candidate_id: UUID
    amount: int
    placed_order: int  # ordinale di piazzamento (per assegnare il remainder)


@dataclass(frozen=True)
class Payout:
    stake_id: UUID
    participant_id: UUID
    amount: int  # payout lordo accreditato


def parimutuel_payouts(
    stakes: list[StakeView], winning_candidates: set[UUID]
) -> list[Payout] | None:
    """Calcola i payout. Ritorna None se non c'è nessuna puntata vincente (→ void)."""
    total_pool = sum(s.amount for s in stakes)
    winners = sorted(
        (s for s in stakes if s.candidate_id in winning_candidates),
        key=lambda s: s.placed_order,
    )
    if not winners or total_pool <= 0:
        return None

    winning_pool = sum(s.amount for s in winners)
    payouts = [
        Payout(
            stake_id=s.stake_id,
            participant_id=s.participant_id,
            amount=(s.amount * total_pool) // winning_pool,
        )
        for s in winners
    ]
    remainder = total_pool - sum(p.amount for p in payouts)
    if remainder > 0:
        first = payouts[0]
        payouts[0] = Payout(
            stake_id=first.stake_id,
            participant_id=first.participant_id,
            amount=first.amount + remainder,
        )
    return payouts
