"""Configurazione applicativa caricata da variabili d'ambiente (.env).

Unica sorgente di verità per i settaggi; i domìni la ricevono via dependency
injection e non leggono l'ambiente direttamente.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    secret_key: str = "change-me-dev-secret-please-rotate"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = "postgresql+asyncpg://whisper:whisper@localhost:5432/whisper"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "whisper"
    s3_secret_key: str = "whisper-secret"
    s3_bucket: str = "whisper-photos"
    s3_region: str = "us-east-1"
    s3_public_url: str = "http://localhost:9000/whisper-photos"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
