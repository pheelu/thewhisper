"""Entità di dominio del contesto `identity` (pure, nessuna dipendenza I/O)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from whisper.shared.core.entity import TimestampedEntity
from whisper.shared.core.enums import EventStatus, ParticipantNobleTitle, ParticipantRole


@dataclass(kw_only=True)
class Event(TimestampedEntity):
    name: str
    venue_name: str | None
    join_code: str
    status: EventStatus
    starts_at: datetime
    ends_at: datetime
    closed_at: datetime | None
    timezone: str
    retention_until: datetime | None
    host_secret_hash: str | None
    settings: dict[str, Any] = field(default_factory=dict)

    def is_within_window(self, now: datetime) -> bool:
        end = self.closed_at or self.ends_at
        return self.starts_at <= now <= end

    def is_joinable(self, now: datetime) -> bool:
        return self.status == EventStatus.open and self.is_within_window(now)


@dataclass(kw_only=True)
class Participant(TimestampedEntity):
    event_id: UUID
    pseudonym: str
    noble_title: ParticipantNobleTitle | None
    role: ParticipantRole
    score: int
    is_photographable: bool
    consent_at: datetime | None
    consent_revoked_at: datetime | None
    session_token_id: UUID
    last_seen_at: datetime | None
    left_at: datetime | None
