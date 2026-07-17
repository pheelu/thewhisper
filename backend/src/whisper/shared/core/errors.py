"""Gerarchia di errori di dominio + mapping a HTTP.

I `core/` sollevano SOLO sottoclassi di `DomainError` (mai `HTTPException` grezza).
Ogni errore porta un `code` stabile e machine-readable `"<dominio>.<slug>"` (NON
localizzato) e un `message` leggibile. Gli handler HTTP (in `infrastructure/http`)
traducono `DomainError` nell'envelope standard.
"""

from typing import Any


class DomainError(Exception):
    """Errore di dominio base. Le sottoclassi fissano lo status HTTP."""

    http_status: int = 400
    default_code: str = "error.domain"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = details or {}


class ValidationError(DomainError):
    http_status = 400
    default_code = "error.validation"


class UnauthorizedError(DomainError):
    http_status = 401
    default_code = "error.unauthorized"


class ForbiddenError(DomainError):
    http_status = 403
    default_code = "error.forbidden"


class NotFoundError(DomainError):
    http_status = 404
    default_code = "error.not_found"


class ConflictError(DomainError):
    http_status = 409
    default_code = "error.conflict"


class EventClosedError(DomainError):
    """L'evento è chiuso: le mutazioni di gioco non sono più ammesse."""

    http_status = 410
    default_code = "event.closed"


class RateLimitedError(DomainError):
    http_status = 429
    default_code = "error.rate_limited"
