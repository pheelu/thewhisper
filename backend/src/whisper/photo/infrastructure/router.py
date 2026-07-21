"""Router HTTP delle Foto Whisper."""

import contextlib
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from whisper.gamification.infrastructure.points_service import PointsService
from whisper.photo.core import use_cases
from whisper.photo.infrastructure import queries
from whisper.photo.infrastructure.repositories import SqlAlchemyPhotoRepository
from whisper.photo.infrastructure.schemas import CreateDraftRequest, CreateDraftResponse
from whisper.shared.core.clock import SystemClock
from whisper.shared.core.errors import NotFoundError
from whisper.shared.core.events import DomainEvent
from whisper.shared.infrastructure.http.deps import (
    Bus,
    CurrentParticipant,
    DbSession,
    Storage,
)
from whisper.shared.infrastructure.realtime.broker import EventBus, RealtimeMessage
from whisper.shared.infrastructure.storage.s3 import S3Storage

router = APIRouter(prefix="/api/v1/photos", tags=["photo"])
_clock = SystemClock()
_IMAGE_TYPES = {"photo.published", "photo.of_you_published"}


async def _attach_images(items: list[dict[str, Any]], storage: S3Storage) -> list[dict[str, Any]]:
    keys = [it["storage_key"] for it in items if it.get("storage_key")]
    urls = await storage.presigned_get_many(keys) if keys else {}
    for it in items:
        key = it.pop("storage_key", None)
        it["image_url"] = urls.get(key) if key else None
    return items


async def _publish(
    bus: EventBus, event_id: UUID, events: list[DomainEvent], *, image_url: str | None = None
) -> None:
    msgs = []
    for e in events:
        payload = e.payload
        if image_url and e.type in _IMAGE_TYPES:
            payload = {**e.payload, "image_url": image_url}
        msgs.append(
            RealtimeMessage(
                event_id=event_id,
                type=e.type,
                payload=payload,
                target_participant_id=e.target_participant_id,
            )
        )
    await bus.publish_many(msgs)


@router.post("", response_model=CreateDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    body: CreateDraftRequest, db: DbSession, context: CurrentParticipant, storage: Storage
) -> CreateDraftResponse:
    photo = await use_cases.create_draft(
        SqlAlchemyPhotoRepository(db),
        _clock,
        event_id=context.event_id,
        hunter_id=context.participant_id,
        subject_id=body.subject_participant_id,
        mysterious_title=body.mysterious_title,
        content_type=body.content_type,
    )
    await db.commit()
    upload_url = await storage.presigned_put(photo.storage_key, content_type=photo.content_type)
    return CreateDraftResponse(
        photo_id=photo.id, upload_url=upload_url, content_type=photo.content_type
    )


@router.post("/{photo_id}/publish")
async def publish(
    photo_id: UUID, db: DbSession, context: CurrentParticipant, bus: Bus, storage: Storage
) -> dict[str, Any]:
    photo, events = await use_cases.publish(
        SqlAlchemyPhotoRepository(db),
        PointsService(db),
        _clock,
        event_id=context.event_id,
        photo_id=photo_id,
        hunter_id=context.participant_id,
    )
    await db.commit()
    # presign best-effort: la foto è già pubblicata e i punti accreditati
    image_url: str | None = None
    with contextlib.suppress(Exception):
        image_url = await storage.presigned_get(photo.storage_key)
    await _publish(bus, context.event_id, events, image_url=image_url)
    item = await queries.detail(db, context.event_id, photo_id)
    return (await _attach_images([item], storage))[0] if item else {"photo_id": str(photo_id)}


@router.get("")
async def get_feed(db: DbSession, context: CurrentParticipant, storage: Storage) -> dict[str, Any]:
    items = await queries.feed(db, context.event_id)
    return {"items": await _attach_images(items, storage)}


@router.get("/mine")
async def get_mine(db: DbSession, context: CurrentParticipant, storage: Storage) -> dict[str, Any]:
    items = await queries.mine(db, context.event_id, context.participant_id)
    return {"items": await _attach_images(items, storage)}


@router.get("/of-me")
async def get_of_me(db: DbSession, context: CurrentParticipant, storage: Storage) -> dict[str, Any]:
    items = await queries.of_me(db, context.event_id, context.participant_id)
    return {"items": await _attach_images(items, storage)}


@router.get("/{photo_id}")
async def get_one(
    photo_id: UUID, db: DbSession, context: CurrentParticipant, storage: Storage
) -> dict[str, Any]:
    item = await queries.detail(db, context.event_id, photo_id)
    if item is None:
        raise NotFoundError("Foto non trovata.", code="photo.not_found")
    return (await _attach_images([item], storage))[0]


@router.post("/{photo_id}/reveal")
async def reveal(
    photo_id: UUID, db: DbSession, context: CurrentParticipant, bus: Bus, storage: Storage
) -> dict[str, Any]:
    photo, events = await use_cases.reveal_subject(
        SqlAlchemyPhotoRepository(db),
        _clock,
        event_id=context.event_id,
        photo_id=photo_id,
        subject_id=context.participant_id,
    )
    await db.commit()
    # arricchisci l'evento con l'identità di gioco del Soggetto
    enriched = []
    for e in events:
        if e.type == "photo.subject_revealed":
            row = (
                await db.execute(
                    text("SELECT pseudonym, noble_title FROM participant WHERE id = :pid"),
                    {"pid": context.participant_id},
                )
            ).one()
            enriched.append(
                DomainEvent(
                    type=e.type,
                    payload={
                        **e.payload,
                        "subject": {
                            "participant_id": str(context.participant_id),
                            "pseudonym": row.pseudonym,
                            "noble_title": row.noble_title,
                        },
                    },
                )
            )
        else:
            enriched.append(e)
    await _publish(bus, context.event_id, enriched)
    item = await queries.detail(db, context.event_id, photo_id)
    return (await _attach_images([item], storage))[0] if item else {"photo_id": str(photo_id)}


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    photo_id: UUID, db: DbSession, context: CurrentParticipant, bus: Bus, storage: Storage
):
    photo, events, storage_key = await use_cases.remove(
        SqlAlchemyPhotoRepository(db),
        _clock,
        event_id=context.event_id,
        photo_id=photo_id,
        actor_id=context.participant_id,
        actor_is_host=context.is_host,
    )
    await db.commit()
    await _publish(bus, context.event_id, events)
    # purge dell'oggetto S3 best-effort: la foto è già rimossa dal feed
    with contextlib.suppress(Exception):
        await storage.delete_object(storage_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
