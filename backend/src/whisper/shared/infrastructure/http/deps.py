"""Dependency FastAPI condivise: sessione DB, participant corrente, ruolo, realtime.

Tutti i router di dominio dipendono da `current_participant`; ogni query di dominio
DEVE poi filtrare per `context.event_id`. Nessun endpoint di gioco accetta
`event_id` dal client.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from whisper.settings import Settings, get_settings
from whisper.shared.core.context import SessionContext
from whisper.shared.core.errors import ForbiddenError, UnauthorizedError
from whisper.shared.infrastructure.db.session import get_session
from whisper.shared.infrastructure.realtime.broker import EventBus
from whisper.shared.infrastructure.realtime.hub import WebSocketHub
from whisper.shared.infrastructure.security.session_auth import verify_session

DbSession = Annotated[AsyncSession, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_hub(request: Request) -> WebSocketHub:
    return request.app.state.hub


Bus = Annotated[EventBus, Depends(get_event_bus)]


def extract_token(request: Request, settings: Settings) -> str | None:
    cookie = request.cookies.get(settings.session_cookie_name)
    if cookie:
        return cookie
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def current_participant(
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> SessionContext:
    token = extract_token(request, settings)
    if not token:
        raise UnauthorizedError("Autenticazione richiesta.", code="session.missing")
    return await verify_session(db, token, settings.secret_key)


CurrentParticipant = Annotated[SessionContext, Depends(current_participant)]


async def require_host(context: CurrentParticipant) -> SessionContext:
    if not context.is_host:
        raise ForbiddenError("Operazione riservata all'organizzatore.", code="session.not_host")
    return context


CurrentHost = Annotated[SessionContext, Depends(require_host)]
