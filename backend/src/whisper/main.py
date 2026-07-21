"""Entry point FastAPI di The Whisper: crea l'app, monta i router, gestisce il
lifespan (WebSocket hub, EventBus, scheduler, storage)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from whisper.settings import Settings

from whisper.betting.infrastructure.job import make_betting_tick
from whisper.betting.infrastructure.router import router as betting_router
from whisper.dialogue.infrastructure.router import router as dialogue_router
from whisper.discovery.infrastructure.router import router as discovery_router
from whisper.gamification.infrastructure.router import router as gamification_router
from whisper.identity.infrastructure.router import router as identity_router
from whisper.photo.infrastructure.router import router as photo_router
from whisper.profile.infrastructure.router import router as profile_router
from whisper.settings import get_settings
from whisper.shared.infrastructure.db.session import dispose_engine
from whisper.shared.infrastructure.http.error_handlers import install_error_handlers
from whisper.shared.infrastructure.realtime.broker import EventBus
from whisper.shared.infrastructure.realtime.hub import WebSocketHub
from whisper.shared.infrastructure.realtime.ws_endpoint import register_ws
from whisper.shared.infrastructure.scheduler.loop import Scheduler
from whisper.shared.infrastructure.storage.s3 import S3Storage

logger = logging.getLogger("whisper")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    hub = WebSocketHub()
    app.state.hub = hub
    app.state.event_bus = EventBus(hub)
    app.state.storage = S3Storage(settings)
    app.state.scheduler = Scheduler(tick_seconds=60.0)

    try:
        await app.state.storage.ensure_bucket()
    except Exception:  # noqa: BLE001 — storage assente in dev: non deve impedire l'avvio
        logger.warning("Storage S3/MinIO non raggiungibile all'avvio.")

    app.state.scheduler.register(
        "betting.tick", make_betting_tick(app.state.event_bus), interval_seconds=60
    )
    app.state.scheduler.start()
    try:
        yield
    finally:
        await app.state.scheduler.stop()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="The Whisper API",
        version="0.1.0",
        summary="Social game real-time del mistero e del corteggiamento",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(identity_router)
    app.include_router(gamification_router)
    app.include_router(profile_router)
    app.include_router(photo_router)
    app.include_router(discovery_router)
    app.include_router(dialogue_router)
    app.include_router(betting_router)
    register_ws(app)
    _mount_frontend(app, settings)
    return app


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
    """Serve la PWA buildata (produzione), con fallback SPA su index.html.

    Registrato DOPO i router API: /api, /health, /docs vengono risolti prima; il
    catch-all serve gli asset statici o l'index per le rotte lato client.
    """
    if not settings.frontend_dist:
        return
    dist = Path(settings.frontend_dist)
    index = dist / "index.html"
    if not index.is_file():
        logger.warning("frontend_dist='%s' non contiene index.html: PWA non servita.", dist)
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(index))


app = create_app()
