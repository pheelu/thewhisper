"""Sorgente del tempo. Vietato `datetime.now()` naive sparso: usare `Clock.now()`.

Il tempo è sempre timezone-aware UTC. `Clock` è iniettabile per rendere i use
case testabili senza dipendere dall'orologio di sistema.
"""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Implementazione di produzione: orologio di sistema, aware UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Orologio fisso per i test."""

    def __init__(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            raise ValueError("FixedClock richiede un datetime timezone-aware")
        self._moment = moment

    def now(self) -> datetime:
        return self._moment
