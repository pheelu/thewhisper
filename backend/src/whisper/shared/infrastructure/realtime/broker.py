"""EventBus interno: i domini pubblicano eventi realtime, l'hub li instrada.

I use case di `core/` restituiscono `DomainEvent` puri; è l'adapter (router) a
tradurli in `RealtimeMessage` e a pubblicarli QUI, sempre DOPO il commit DB
(ordine vincolante persist→publish).
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from whisper.shared.infrastructure.realtime.envelope import build_envelope
from whisper.shared.infrastructure.realtime.hub import WebSocketHub


@dataclass(frozen=True)
class RealtimeMessage:
    event_id: UUID
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    # None = broadcast a tutta la room; altrimenti recapito mirato al participant.
    target_participant_id: UUID | None = None


class EventBus:
    def __init__(self, hub: WebSocketHub) -> None:
        self._hub = hub

    async def publish(self, message: RealtimeMessage) -> None:
        envelope = build_envelope(
            type=message.type, payload=message.payload, event_id=message.event_id
        )
        if message.target_participant_id is None:
            await self._hub.broadcast(message.event_id, envelope)
        else:
            await self._hub.send_to_participant(
                message.event_id, message.target_participant_id, envelope
            )

    async def publish_many(self, messages: list[RealtimeMessage]) -> None:
        for message in messages:
            await self.publish(message)
