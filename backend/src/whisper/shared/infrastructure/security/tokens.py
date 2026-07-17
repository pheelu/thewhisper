"""Firma/verifica del session token (JWT HS256), event-scoped.

Nessuna tabella di sessione: la revoca avviene rigenerando `participant.session_token_id`
(il claim `jti`) e verificando che coincida (vedi `session_auth`).
"""

from datetime import datetime
from uuid import UUID

import jwt

ALGORITHM = "HS256"


def issue_session_token(
    *,
    participant_id: UUID,
    event_id: UUID,
    role: str,
    jti: UUID,
    issued_at: datetime,
    expires_at: datetime,
    secret: str,
) -> str:
    payload = {
        "sub": str(participant_id),
        "eid": str(event_id),
        "role": str(role),
        "jti": str(jti),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_session_token(token: str, secret: str) -> dict:
    """Decodifica e verifica firma/scadenza. Solleva `jwt.PyJWTError` se invalido."""
    return jwt.decode(token, secret, algorithms=[ALGORITHM])
