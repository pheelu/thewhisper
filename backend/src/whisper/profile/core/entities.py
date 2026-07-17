"""Entità di dominio del profilo nobiliare."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from whisper.profile.core.enums import ProfileRevealStage
from whisper.shared.core.entity import TimestampedEntity


@dataclass(kw_only=True)
class Profile(TimestampedEntity):
    event_id: UUID
    participant_id: UUID
    secret_text: str | None
    motto: str | None
    avatar_seed: str
    accent_color: str | None
    clues: list[Any] = field(default_factory=list)
    reveal_stage: ProfileRevealStage
    is_complete: bool
    completed_at: datetime | None
    disclosed_publicly_at: datetime | None

    def compute_complete(self) -> bool:
        return bool(self.secret_text and self.secret_text.strip() and self.motto and self.motto.strip())
