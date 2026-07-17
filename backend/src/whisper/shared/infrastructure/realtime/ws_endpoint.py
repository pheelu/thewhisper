"""Endpoint WebSocket unico `/api/v1/ws`: autentica il socket e lo iscrive alla room.

Autenticazione identica al canale HTTP (cookie httpOnly primario, primo frame
`auth` come fallback). Isolamento per-evento: una room = un evento.
"""

import asyncio
import contextlib

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from whisper.settings import get_settings
from whisper.shared.core.errors import UnauthorizedError
from whisper.shared.infrastructure.db.session import SessionFactory
from whisper.shared.infrastructure.realtime.envelope import build_envelope
from whisper.shared.infrastructure.security.session_auth import verify_session

_AUTH_FRAME_TIMEOUT = 5.0


async def _resolve_token(websocket: WebSocket, cookie_name: str) -> str | None:
    token = websocket.cookies.get(cookie_name)
    if token:
        return token
    try:
        msg = await asyncio.wait_for(websocket.receive_json(), timeout=_AUTH_FRAME_TIMEOUT)
    except (TimeoutError, WebSocketDisconnect, ValueError):
        return None
    if isinstance(msg, dict) and msg.get("type") == "auth":
        payload = msg.get("payload") or {}
        return payload.get("token")
    return None


async def whisper_ws(websocket: WebSocket) -> None:
    settings = get_settings()
    hub = websocket.app.state.hub
    await websocket.accept()

    token = await _resolve_token(websocket, settings.session_cookie_name)
    if not token:
        await websocket.close(code=4401)
        return

    async with SessionFactory() as db:
        try:
            context = await verify_session(db, token, settings.secret_key)
        except UnauthorizedError:
            await websocket.close(code=4401)
            return

    await hub.connect(context.event_id, context.participant_id, websocket)
    await websocket.send_json(
        build_envelope(
            type="session.ready",
            payload={"participant_id": str(context.participant_id)},
            event_id=context.event_id,
        )
    )
    await hub.broadcast(
        context.event_id,
        build_envelope(
            type="presence.updated",
            payload={"active": [str(pid) for pid in hub.presence(context.event_id)]},
            event_id=context.event_id,
        ),
    )

    try:
        while True:
            msg = await websocket.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await websocket.send_json(
                    build_envelope(type="pong", payload={}, event_id=context.event_id)
                )
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(context.event_id, context.participant_id, websocket)
        with contextlib.suppress(Exception):
            await hub.broadcast(
                context.event_id,
                build_envelope(
                    type="presence.updated",
                    payload={"active": [str(pid) for pid in hub.presence(context.event_id)]},
                    event_id=context.event_id,
                ),
            )


def register_ws(app: FastAPI) -> None:
    app.add_api_websocket_route("/api/v1/ws", whisper_ws)
