"""DomainEvent: evento di dominio puro emesso dai use case.

`core/` non conosce il WebSocket: ritorna `DomainEvent`; l'adapter (router) li
traduce in `RealtimeMessage` e li pubblica sull'EventBus dopo il commit.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class DomainEvent:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    # None = broadcast alla room; altrimenti recapito mirato.
    target_participant_id: UUID | None = None
