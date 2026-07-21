"""Configurazione applicativa (pydantic-settings): unica sorgente di config/env.

I domini ricevono i valori via dependency injection e non leggono l'ambiente
direttamente.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field
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
    # URL pubblico dell'app (per link di join/QR). Render lo fornisce come
    # RENDER_EXTERNAL_URL; in dev resta vuoto e si usa l'origine del frontend.
    public_base_url: str = Field(
        default="", validation_alias=AliasChoices("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL")
    )

    # --- Database ---
    database_url: str = "postgresql+asyncpg://whisper:whisper@localhost:5432/whisper"
    db_echo: bool = False
    # Disabilita i prepared statement di asyncpg: necessario dietro un pooler in
    # transaction mode (es. Supabase Transaction pooler / PgBouncer).
    db_disable_prepared_statements: bool = False

    # --- Frontend statico (produzione: il backend serve la PWA buildata) ---
    # Path alla cartella `dist` del frontend; se esiste, viene servita su "/".
    frontend_dist: str = ""

    # --- Sessione / cookie ---
    session_cookie_name: str = "whisper_session"
    session_cookie_secure: bool = False  # True in produzione (HTTPS)
    session_cookie_samesite: str = "lax"
    # Margine oltre la fine evento entro cui il token resta valido (ore).
    session_grace_hours: int = 6

    # --- S3 / MinIO ---
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "whisper"
    s3_secret_key: str = "whisper-secret"
    s3_bucket: str = "whisper-photos"
    s3_region: str = "us-east-1"
    s3_public_url: str = "http://localhost:9000/whisper-photos"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
