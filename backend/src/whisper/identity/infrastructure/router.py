"""Router HTTP del dominio identity: /events, /join, /me, /me/consent."""

import contextlib
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Response, status

from whisper.identity.core import use_cases
from whisper.identity.core.entities import Event, Participant
from whisper.identity.infrastructure.repositories import (
    SqlAlchemyEventRepository,
    SqlAlchemyParticipantRepository,
)
from whisper.identity.infrastructure.schemas import (
    ConsentRequest,
    CreateEventRequest,
    CreateEventResponse,
    EventHostView,
    HostSessionRequest,
    HostSessionResponse,
    JoinRequest,
    JoinResponse,
    MeResponse,
    ParticipantPublic,
    event_host_view,
    event_public,
    participant_public,
)
from whisper.identity.infrastructure.security import hash_secret, verify_secret
from whisper.settings import Settings
from whisper.shared.core.clock import SystemClock
from whisper.shared.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from whisper.shared.core.events import DomainEvent
from whisper.shared.infrastructure.http.deps import (
    AppSettings,
    Bus,
    CurrentParticipant,
    DbSession,
    Storage,
)
from whisper.shared.infrastructure.realtime.broker import EventBus, RealtimeMessage

router = APIRouter(prefix="/api/v1", tags=["identity"])
_clock = SystemClock()


# ---------- helper ----------
def _token_expiry(event: Event, settings: Settings, now: datetime) -> datetime:
    exp = event.ends_at + timedelta(hours=settings.session_grace_hours)
    return exp if exp > now else now + timedelta(hours=settings.session_grace_hours)


def _issue_token(participant: Participant, event: Event, settings: Settings, now: datetime) -> str:
    from whisper.shared.infrastructure.security.tokens import issue_session_token

    exp = _token_expiry(event, settings, now)
    return issue_session_token(
        participant_id=participant.id,
        event_id=event.id,
        role=str(participant.role),
        jti=participant.session_token_id,
        issued_at=now,
        expires_at=exp,
        secret=settings.secret_key,
    )


def _set_session_cookie(
    response: Response, settings: Settings, token: str, event: Event, now: datetime
) -> None:
    max_age = int((_token_expiry(event, settings, now) - now).total_seconds())
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _join_url(settings: Settings, join_code: str) -> str:
    if settings.public_base_url:
        base = settings.public_base_url.rstrip("/")
    else:
        origins = settings.cors_origin_list
        base = origins[0].rstrip("/") if origins else ""
    return f"{base}/j/{join_code}"


async def _publish(bus: EventBus, event_id: UUID, events: list[DomainEvent]) -> None:
    await bus.publish_many(
        [
            RealtimeMessage(
                event_id=event_id,
                type=e.type,
                payload=e.payload,
                target_participant_id=e.target_participant_id,
            )
            for e in events
        ]
    )


# ---------- eventi (host) ----------
@router.post("/events", response_model=CreateEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: CreateEventRequest, response: Response, db: DbSession, settings: AppSettings
) -> CreateEventResponse:
    event_repo = SqlAlchemyEventRepository(db)
    participant_repo = SqlAlchemyParticipantRepository(db)
    event, host = await use_cases.create_event(
        event_repo,
        participant_repo,
        _clock,
        name=body.name,
        venue_name=body.venue_name,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        timezone=body.timezone,
        host_secret_hash=hash_secret(body.host_secret),
        host_pseudonym=body.host_pseudonym,
    )
    await db.commit()

    now = _clock.now()
    token = _issue_token(host, event, settings, now)
    _set_session_cookie(response, settings, token, event, now)
    return CreateEventResponse(
        event=event_host_view(event),
        host=participant_public(host),
        host_token=token,
        join_url=_join_url(settings, event.join_code),
    )


async def _load_event_for_host(db, context, event_id: UUID) -> Event:
    if context.event_id != event_id:
        raise ForbiddenError("Non sei l'organizzatore di questa serata.", code="event.forbidden")
    event = await SqlAlchemyEventRepository(db).get(event_id)
    if event is None:
        raise NotFoundError("Serata non trovata.", code="event.not_found")
    return event


@router.post("/events/{event_id}/open", response_model=EventHostView)
async def open_event(event_id: UUID, db: DbSession, context: CurrentParticipant) -> EventHostView:
    if not context.is_host:
        raise ForbiddenError("Operazione riservata all'organizzatore.", code="session.not_host")
    event = await _load_event_for_host(db, context, event_id)
    event = await use_cases.open_event(SqlAlchemyEventRepository(db), _clock, event)
    await db.commit()
    return event_host_view(event)


@router.post("/events/{event_id}/close", response_model=EventHostView)
async def close_event(
    event_id: UUID, db: DbSession, context: CurrentParticipant, bus: Bus
) -> EventHostView:
    if not context.is_host:
        raise ForbiddenError("Operazione riservata all'organizzatore.", code="session.not_host")
    event = await _load_event_for_host(db, context, event_id)
    event, events = await use_cases.close_event(
        SqlAlchemyEventRepository(db), SqlAlchemyParticipantRepository(db), _clock, event
    )
    await db.commit()
    await _publish(bus, event.id, events)
    return event_host_view(event)


@router.get("/events/{event_id}/qr.png", include_in_schema=False)
async def event_qr(
    event_id: UUID, db: DbSession, context: CurrentParticipant, settings: AppSettings
):
    """QR del link di ingresso (PNG). Visibile all'host della serata."""
    import io

    import qrcode
    from fastapi import Response as FastAPIResponse

    if not context.is_host or context.event_id != event_id:
        raise ForbiddenError("Operazione riservata all'organizzatore.", code="session.not_host")
    event = await SqlAlchemyEventRepository(db).get(event_id)
    if event is None:
        raise NotFoundError("Serata non trovata.", code="event.not_found")

    img = qrcode.make(_join_url(settings, event.join_code), box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return FastAPIResponse(content=buf.getvalue(), media_type="image/png")


@router.post("/events/{event_id}/host-session", response_model=HostSessionResponse)
async def host_session(
    event_id: UUID,
    body: HostSessionRequest,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> HostSessionResponse:
    event_repo = SqlAlchemyEventRepository(db)
    participant_repo = SqlAlchemyParticipantRepository(db)
    event = await event_repo.get(event_id)
    if event is None:
        raise NotFoundError("Serata non trovata.", code="event.not_found")
    if not verify_secret(body.host_secret, event.host_secret_hash):
        raise UnauthorizedError("Segreto host non valido.", code="event.bad_host_secret")
    host = await participant_repo.get_host(event.id)
    if host is None:
        raise NotFoundError("Organizzatore non trovato.", code="event.host_missing")
    host = await use_cases.rotate_host_session(participant_repo, _clock, host)
    await db.commit()

    now = _clock.now()
    token = _issue_token(host, event, settings, now)
    _set_session_cookie(response, settings, token, event, now)
    return HostSessionResponse(event=event_host_view(event), host_token=token)


# ---------- join / me (guest) ----------
@router.post("/join", response_model=JoinResponse, status_code=status.HTTP_201_CREATED)
async def join(
    body: JoinRequest, response: Response, db: DbSession, settings: AppSettings
) -> JoinResponse:
    event, participant = await use_cases.join_via_qr(
        SqlAlchemyEventRepository(db),
        SqlAlchemyParticipantRepository(db),
        _clock,
        join_code=body.join_code,
        pseudonym=body.pseudonym,
        noble_title=body.noble_title,
        is_photographable=body.is_photographable,
    )
    await db.commit()

    now = _clock.now()
    token = _issue_token(participant, event, settings, now)
    _set_session_cookie(response, settings, token, event, now)
    return JoinResponse(participant=participant_public(participant), event=event_public(event))


@router.get("/me", response_model=MeResponse)
async def me(db: DbSession, context: CurrentParticipant) -> MeResponse:
    participant = await SqlAlchemyParticipantRepository(db).get(
        context.event_id, context.participant_id
    )
    event = await SqlAlchemyEventRepository(db).get(context.event_id)
    if participant is None or event is None:
        raise NotFoundError("Sessione non valida.", code="session.unknown")
    return MeResponse(participant=participant_public(participant), event=event_public(event))


@router.post("/me/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave(db: DbSession, context: CurrentParticipant, settings: AppSettings) -> Response:
    repo = SqlAlchemyParticipantRepository(db)
    participant = await repo.get(context.event_id, context.participant_id)
    if participant is not None:
        await use_cases.leave_event(repo, _clock, participant)
        await db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response


@router.post("/me/consent", response_model=ParticipantPublic)
async def set_consent(
    body: ConsentRequest,
    db: DbSession,
    context: CurrentParticipant,
    bus: Bus,
    storage: Storage,
) -> ParticipantPublic:
    repo = SqlAlchemyParticipantRepository(db)
    participant = await repo.get(context.event_id, context.participant_id)
    if participant is None:
        raise NotFoundError("Partecipante non trovato.", code="participant.not_found")
    result = await use_cases.set_consent(
        repo, _clock, participant, is_photographable=body.is_photographable
    )

    # Cascata GDPR sulla revoca: le foto attive che ritraggono il partecipante
    # vengono rimosse (composizione a livello adapter via PhotoService, senza
    # svelare il Cacciatore).
    removed: list[tuple[UUID, str]] = []
    if not body.is_photographable:
        from whisper.photo.infrastructure.photo_port import PhotoService

        removed = await PhotoService(db).remove_all_of_subject(
            context.event_id, context.participant_id
        )
        result.events.extend(
            DomainEvent(type="photo.removed", payload={"photo_id": str(photo_id)})
            for photo_id, _key in removed
        )

    await db.commit()
    await _publish(bus, context.event_id, result.events)
    for _photo_id, key in removed:
        with contextlib.suppress(Exception):  # purge best-effort
            await storage.delete_object(key)
    return participant_public(result.participant)
