"""Basi per le entità di dominio (dataclass pure, nessuna dipendenza da I/O).

Uso `kw_only=True` così le sottoclassi possono aggiungere campi obbligatori senza
incorrere nel vincolo di ordinamento dei default dei dataclass.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(kw_only=True)
class BaseEntity:
    id: UUID


@dataclass(kw_only=True)
class TimestampedEntity(BaseEntity):
    created_at: datetime
    updated_at: datetime
