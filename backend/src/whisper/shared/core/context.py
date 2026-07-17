"""Contesto di sessione derivato dal token: identità di gioco scopata all'evento.

È il SOLO modo con cui i domini conoscono "chi" e "in quale evento". Nessun
endpoint di gioco accetta `event_id`/`participant_id` dal client: vengono da qui.
"""

from dataclasses import dataclass
from uuid import UUID

from whisper.shared.core.enums import ParticipantRole


@dataclass(frozen=True)
class SessionContext:
    participant_id: UUID
    event_id: UUID
    role: ParticipantRole

    @property
    def is_host(self) -> bool:
        return self.role == ParticipantRole.host
