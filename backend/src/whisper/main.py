"""Entry point FastAPI di The Whisper: crea l'app, monta i router, gestisce il
lifespan (WebSocket hub, EventBus, scheduler, storage)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    register_ws(app)
    return app


app = create_app()
