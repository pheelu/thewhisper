"""Busta standard dei messaggi realtime: {type, payload, event_id, message_id, ts}."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from whisper.shared.core.ids import uuid7


def _iso_z(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def build_envelope(*, type: str, payload: dict[str, Any], event_id: UUID) -> dict[str, Any]:
    return {
        "type": type,
        "payload": payload,
        "event_id": str(event_id),
        "message_id": str(uuid7()),
        "ts": _iso_z(datetime.now(UTC)),
    }
