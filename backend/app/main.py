"""Entry point FastAPI di The Whisper.

I router di dominio verranno montati qui man mano che i domìni vengono
implementati (profiles, whispers, discovery, messaging, bets, gamification,
gazette, moderation).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="The Whisper API",
        version="0.1.0",
        summary="Social game real-time del mistero e del corteggiamento",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
