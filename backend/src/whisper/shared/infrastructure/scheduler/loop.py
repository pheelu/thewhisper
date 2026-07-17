"""Scheduler unico: un tick asyncio in-process che esegue job registrati dai domini.

MVP single-worker. Ogni dominio registra un job idempotente con la propria cadenza
(scommesse, gazzettino, scadenza inviti, retention...). Un job che lancia
un'eccezione viene loggato e non ferma il loop.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("whisper.scheduler")

JobFn = Callable[[], Awaitable[None]]


@dataclass
class Job:
    name: str
    fn: JobFn
    interval_seconds: float
    elapsed: float = field(default=0.0)


class Scheduler:
    def __init__(self, tick_seconds: float = 60.0) -> None:
        self._tick = tick_seconds
        self._jobs: list[Job] = []
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    def register(self, name: str, fn: JobFn, *, interval_seconds: float) -> None:
        self._jobs.append(Job(name=name, fn=fn, interval_seconds=interval_seconds))

    async def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self._tick)
                break  # stop richiesto
            except TimeoutError:
                pass  # tick normale
            for job in self._jobs:
                job.elapsed += self._tick
                if job.elapsed + 1e-6 >= job.interval_seconds:
                    job.elapsed = 0.0
                    try:
                        await job.fn()
                    except Exception:  # noqa: BLE001 — un job non deve fermare il loop
                        logger.exception("Job scheduler '%s' fallito", job.name)

    def start(self) -> None:
        if self._task is None:
            self._stopped.clear()
            self._task = asyncio.create_task(self._run(), name="whisper-scheduler")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            await self._task
            self._task = None
