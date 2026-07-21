"""Enum di dominio delle scommesse."""

from enum import StrEnum


class BetRoundStatus(StrEnum):
    scheduled = "scheduled"
    open = "open"  # si può puntare
    locked = "locked"  # puntate chiuse, finestra di misurazione in corso
    settled = "settled"  # risolto, payout erogati
    void = "void"  # annullato, puntate rimborsate


class BetStakeStatus(StrEnum):
    placed = "placed"
    won = "won"
    lost = "lost"
    refunded = "refunded"  # rimborso da round void / nessun vincitore
    cancelled = "cancelled"  # annullata dal giocatore prima del lock
