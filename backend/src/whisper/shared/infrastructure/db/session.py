"""Engine async, session factory e dependency `get_session`.

`get_session` fornisce una `AsyncSession` con rollback automatico su eccezione ma
SENZA commit implicito: gli handler committano esplicitamente prima di pubblicare
sul realtime (ordine vincolante persist→publish).
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from whisper.settings import get_settings

_settings = get_settings()

# Dietro un pooler in transaction mode (es. Supabase Transaction pooler / PgBouncer)
# i prepared statement vanno disabilitati sia lato asyncpg sia lato dialetto SQLAlchemy.
_connect_args: dict = {}
if _settings.db_disable_prepared_statements:
    _connect_args = {"statement_cache_size": 0, "prepared_statement_cache_size": 0}

engine: AsyncEngine = create_async_engine(
    _settings.database_url,
    echo=_settings.db_echo,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await engine.dispose()
