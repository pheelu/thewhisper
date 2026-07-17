"""Use case delle Foto Whisper: bozza, pubblicazione (gate consenso), reveal, rimozione."""

from uuid import UUID

from whisper.photo.core.entities import Photo
from whisper.photo.core.enums import PhotoRemovalReason, PhotoStatus
from whisper.photo.core.repositories import PhotoRepository
from whisper.shared.core.clock import Clock
from whisper.shared.core.enums import PointReason
from whisper.shared.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from whisper.shared.core.events import DomainEvent
from whisper.shared.core.ids import uuid7
from whisper.shared.core.ports import PointsPort

PHOTO_CREATED_POINTS = 5
_CONTENT_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


async def create_draft(
    repo: PhotoRepository,
    clock: Clock,
    *,
    event_id: UUID,
    hunter_id: UUID,
    subject_id: UUID,
    mysterious_title: str,
    content_type: str,
) -> Photo:
    if content_type not in _CONTENT_EXT:
        raise ValidationError("Formato immagine non supportato.", code="photo.bad_content_type")
    if subject_id == hunter_id:
        raise ValidationError("Non puoi fotografare te stesso.", code="photo.self_subject")

    state = await repo.get_subject_state(event_id, subject_id)
    if state is None or not state.is_guest:
        raise NotFoundError("Soggetto non valido.", code="photo.subject_not_found")
    if not state.can_be_photographed:
        raise ForbiddenError(
            "Questa persona non ha acconsentito a essere fotografata.",
            code="photo.subject_not_consenting",
        )

    now = clock.now()
    photo_id = uuid7()
    storage_key = f"events/{event_id}/photos/{photo_id}.{_CONTENT_EXT[content_type]}"
    photo = Photo(
        id=photo_id,
        event_id=event_id,
        hunter_participant_id=hunter_id,
        subject_participant_id=subject_id,
        mysterious_title=mysterious_title,
        storage_key=storage_key,
        content_type=content_type,
        status=PhotoStatus.draft,
        subject_revealed=False,
        revealed_at=None,
        published_at=None,
        removed_at=None,
        removed_reason=None,
        removed_by_participant_id=None,
        comment_count=0,
        correct_guess_count=0,
        created_at=now,
        updated_at=now,
    )
    await repo.add(photo)
    return photo


async def _load_owned(repo: PhotoRepository, event_id: UUID, photo_id: UUID) -> Photo:
    photo = await repo.get(event_id, photo_id)
    if photo is None:
        raise NotFoundError("Foto non trovata.", code="photo.not_found")
    return photo


async def publish(
    repo: PhotoRepository,
    points: PointsPort,
    clock: Clock,
    *,
    event_id: UUID,
    photo_id: UUID,
    hunter_id: UUID,
) -> tuple[Photo, list[DomainEvent]]:
    photo = await _load_owned(repo, event_id, photo_id)
    if photo.hunter_participant_id != hunter_id:
        raise ForbiddenError("Non sei l'autore di questa foto.", code="photo.not_owner")
    if photo.status != PhotoStatus.draft:
        raise ConflictError("La foto non è in bozza.", code="photo.invalid_transition")

    state = await repo.get_subject_state(event_id, photo.subject_participant_id)
    if state is None or not state.can_be_photographed:
        raise ConflictError(
            "Il Soggetto ha revocato il consenso.", code="photo.subject_consent_revoked"
        )

    now = clock.now()
    photo.status = PhotoStatus.published
    photo.published_at = now
    photo.updated_at = now
    await repo.update(photo)

    result = await points.award_points(
        event_id=event_id,
        participant_id=hunter_id,
        delta=PHOTO_CREATED_POINTS,
        reason=PointReason.photo_created,
        source_domain="photo",
        idempotency_key=f"photo_created:{photo_id}",
        metadata={"photo_id": str(photo_id)},
    )

    events: list[DomainEvent] = [
        DomainEvent(
            type="photo.published",
            payload={
                "photo_id": str(photo_id),
                "mysterious_title": photo.mysterious_title,
                "published_at": now.isoformat(),
                "comment_count": 0,
                "correct_guess_count": 0,
                "subject_revealed": False,
            },
        ),
        DomainEvent(
            type="photo.of_you_published",
            payload={
                "photo_id": str(photo_id),
                "mysterious_title": photo.mysterious_title,
                "published_at": now.isoformat(),
            },
            target_participant_id=photo.subject_participant_id,
        ),
    ]
    events.extend(result.events)
    return photo, events


async def reveal_subject(
    repo: PhotoRepository,
    clock: Clock,
    *,
    event_id: UUID,
    photo_id: UUID,
    subject_id: UUID,
) -> tuple[Photo, list[DomainEvent]]:
    photo = await _load_owned(repo, event_id, photo_id)
    if photo.subject_participant_id != subject_id:
        raise ForbiddenError("Non sei il Soggetto di questa foto.", code="photo.not_subject")
    if photo.status != PhotoStatus.published:
        raise ConflictError("La foto non è pubblicata.", code="photo.invalid_transition")
    if photo.subject_revealed:
        return photo, []

    now = clock.now()
    photo.subject_revealed = True
    photo.revealed_at = now
    photo.updated_at = now
    await repo.update(photo)

    return photo, [
        DomainEvent(
            type="photo.subject_revealed",
            payload={
                "photo_id": str(photo_id),
                "subject_participant_id": str(subject_id),
                "revealed_at": now.isoformat(),
            },
        )
    ]


async def remove(
    repo: PhotoRepository,
    clock: Clock,
    *,
    event_id: UUID,
    photo_id: UUID,
    actor_id: UUID,
    actor_is_host: bool,
) -> tuple[Photo, list[DomainEvent], str]:
    photo = await _load_owned(repo, event_id, photo_id)

    if actor_is_host:
        reason = PhotoRemovalReason.host_action
    elif actor_id == photo.subject_participant_id:
        reason = PhotoRemovalReason.subject_request
    elif actor_id == photo.hunter_participant_id:
        reason = PhotoRemovalReason.hunter_deleted
    else:
        raise ForbiddenError("Non puoi rimuovere questa foto.", code="photo.remove_forbidden")

    if photo.status == PhotoStatus.removed:
        return photo, [], photo.storage_key

    now = clock.now()
    photo.status = PhotoStatus.removed
    photo.removed_at = now
    photo.removed_reason = reason
    photo.removed_by_participant_id = actor_id
    photo.updated_at = now
    await repo.update(photo)

    # payload volutamente minimale: nessun motivo/attore (discrezione).
    return photo, [DomainEvent(type="photo.removed", payload={"photo_id": str(photo_id)})], photo.storage_key
