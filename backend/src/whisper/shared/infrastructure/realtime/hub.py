"""WebSocketHub: room per-evento (isolamento tenant anche sul realtime).

MVP in-process (single worker). I domini NON parlano mai direttamente ai socket:
pubblicano sull'EventBus, che instrada qui. Un partecipante può avere più tab
(più socket) nella stessa room.
"""

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

from starlette.websockets import WebSocket


class WebSocketHub:
    def __init__(self) -> None:
        # event_id -> participant_id -> set[WebSocket]
        self._rooms: dict[UUID, dict[UUID, set[WebSocket]]] = defaultdict(lambda: defaultdict(set))
        self._lock = asyncio.Lock()

    async def connect(self, event_id: UUID, participant_id: UUID, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[event_id][participant_id].add(ws)

    async def disconnect(self, event_id: UUID, participant_id: UUID, ws: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(event_id)
            if not room:
                return
            sockets = room.get(participant_id)
            if sockets:
                sockets.discard(ws)
                if not sockets:
                    del room[participant_id]
            if not room:
                del self._rooms[event_id]

    def _snapshot(self, event_id: UUID) -> dict[UUID, set[WebSocket]]:
        room = self._rooms.get(event_id, {})
        return {pid: set(socks) for pid, socks in room.items()}

    async def _safe_send(self, ws: WebSocket, message: dict[str, Any]) -> None:
        try:
            await ws.send_json(message)
        except Exception:  # noqa: BLE001 — socket morto/chiuso: best-effort, lo ignoriamo
            pass

    async def broadcast(self, event_id: UUID, message: dict[str, Any]) -> None:
        targets = [ws for socks in self._snapshot(event_id).values() for ws in socks]
        await asyncio.gather(*(self._safe_send(ws, message) for ws in targets))

    async def send_to_participant(
        self, event_id: UUID, participant_id: UUID, message: dict[str, Any]
    ) -> None:
        sockets = self._snapshot(event_id).get(participant_id, set())
        await asyncio.gather(*(self._safe_send(ws, message) for ws in sockets))

    def presence(self, event_id: UUID) -> list[UUID]:
        return list(self._rooms.get(event_id, {}).keys())
