"""Verifica end-to-end del session token contro lo stato del DB → `SessionContext`.

Logica condivisa tra la dependency HTTP `current_participant` e l'handshake del
WebSocket, così l'autenticazione è identica sui due canali. Usa SQL grezzo per NON
importare i modelli ORM del dominio `identity` (rispetto del layering).
"""

from uuid import UUID

import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.shared.core.context import SessionContext
from whisper.shared.core.enums import EventStatus, ParticipantRole
from whisper.shared.core.errors import UnauthorizedError
from whisper.shared.infrastructure.security.tokens import decode_session_token

# L'evento deve essere in uno di questi stati perché la sessione sia valida.
# `draft`: solo l'host ha un token (bootstrap, per poter aprire l'evento) —
# i guest ottengono un token solo su eventi `open`.
# `closed`: consente sola lettura (es. gazzettino finale). `archived` esclude.
_VALID_EVENT_STATUSES = {
    EventStatus.draft.value,
    EventStatus.open.value,
    EventStatus.closed.value,
}

_LOOKUP_SQL = text(
    """
    SELECT p.session_token_id, p.role, p.left_at, e.status
    FROM participant p
    JOIN event e ON e.id = p.event_id
    WHERE p.id = :pid AND p.event_id = :eid
    """
)


async def verify_session(db: AsyncSession, token: str, secret: str) -> SessionContext:
    try:
        claims = decode_session_token(token, secret)
        participant_id = UUID(claims["sub"])
        event_id = UUID(claims["eid"])
        jti = claims["jti"]
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Sessione non valida o scaduta.", code="session.invalid") from exc

    row = (await db.execute(_LOOKUP_SQL, {"pid": participant_id, "eid": event_id})).first()
    if row is None:
        raise UnauthorizedError("Partecipante non trovato.", code="session.unknown")

    session_token_id, role, left_at, status = row
    if str(session_token_id) != str(jti):
        raise UnauthorizedError("Sessione revocata.", code="session.revoked")
    if left_at is not None:
        raise UnauthorizedError("Hai lasciato la serata.", code="session.left")
    if status not in _VALID_EVENT_STATUSES:
        raise UnauthorizedError("La serata non è disponibile.", code="session.event_unavailable")

    return SessionContext(
        participant_id=participant_id,
        event_id=event_id,
        role=ParticipantRole(role),
    )
