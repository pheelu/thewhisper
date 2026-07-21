"""Paginazione cursor-based (keyset), non offset.

Ordine di default `created_at DESC, id DESC`. Il cursore è opaco (base64 di
`created_at|id`) e viene interpretato dai repository.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass(frozen=True)
class Cursor:
    created_at: datetime
    id: UUID

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}|{self.id}"
        return base64.urlsafe_b64encode(raw.encode()).decode()

    @classmethod
    def decode(cls, token: str) -> Cursor:
        try:
            raw = base64.urlsafe_b64decode(token.encode()).decode()
            ts, uid = raw.split("|", 1)
            return cls(created_at=datetime.fromisoformat(ts), id=UUID(uid))
        except Exception as exc:  # noqa: BLE001 — cursore malformato = 400 lato router
            raise ValueError("Cursore di paginazione non valido") from exc


@dataclass(frozen=True)
class PageParams:
    limit: int = DEFAULT_LIMIT
    cursor: str | None = None

    def normalized_limit(self) -> int:
        return max(1, min(self.limit, MAX_LIMIT))

    def decoded_cursor(self) -> Cursor | None:
        return Cursor.decode(self.cursor) if self.cursor else None


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    next_cursor: str | None
    limit: int
