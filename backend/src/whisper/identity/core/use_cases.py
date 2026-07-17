"""Use case del dominio identity: creazione/apertura/chiusura evento, join, consenso.

Ricevono i repository (Protocol) e il `Clock` per dependency injection. Restituiscono
entità e, dove serve, `DomainEvent` puri che il router pubblica sul realtime.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from whisper.identity.core.entities import Event, Participant
from whisper.identity.core.repositories import EventRepository, ParticipantRepository
from whisper.identity.core.services import generate_join_code
from whisper.shared.core.clock import Clock
from whisper.shared.core.enums import EventStatus, ParticipantNobleTitle, ParticipantRole
from whisper.shared.core.errors import ConflictError, EventClosedError, NotFoundError
from whisper.shared.core.events import DomainEvent
from whisper.shared.core.ids import uuid7

RETENTION_DAYS = 30
_JOIN_CODE_ATTEMPTS = 8


@dataclass
class ConsentResult:
    participant: Participant
    events: list[DomainEvent] = field(default_factory=list)


async def create_event(
    event_repo: EventRepository,
    participant_repo: ParticipantRepository,
    clock: Clock,
    *,
    name: str,
    venue_name: str | None,
    starts_at,
    ends_at,
    timezone: str,
    host_secret_hash: str,
    host_pseudonym: str,
) -> tuple[Event, Participant]:
    now = clock.now()

    join_code = await _unique_join_code(event_repo)
    event = Event(
        id=uuid7(),
        name=name,
        venue_name=venue_name,
        join_code=join_code,
        status=EventStatus.draft,
        starts_at=starts_at,
        ends_at=ends_at,
        closed_at=None,
        timezone=timezone,
        retention_until=None,
        host_secret_hash=host_secret_hash,
        settings={},
        created_at=now,
        updated_at=now,
    )
    await event_repo.add(event)

    host = Participant(
        id=uuid7(),
        event_id=event.id,
        pseudonym=host_pseudonym,
        noble_title=None,
        role=ParticipantRole.host,
        score=0,
        is_photographable=False,
        consent_at=None,
        consent_revoked_at=None,
        session_token_id=uuid7(),
        last_seen_at=None,
        left_at=None,
        created_at=now,
        updated_at=now,
    )
    await participant_repo.add(host)
    return event, host


async def _unique_join_code(event_repo: EventRepository) -> str:
    for _ in range(_JOIN_CODE_ATTEMPTS):
        code = generate_join_code()
        if await event_repo.get_by_join_code(code) is None:
            return code
    raise ConflictError("Impossibile generare un codice evento univoco.", code="event.code_clash")


async def open_event(event_repo: EventRepository, clock: Clock, event: Event) -> Event:
    if event.status == EventStatus.open:
        return event
    if event.status != EventStatus.draft:
        raise ConflictError("L'evento non può essere aperto da questo stato.", code="event.not_openable")
    event.status = EventStatus.open
    event.updated_at = clock.now()
    await event_repo.update(event)
    return event


async def close_event(
    event_repo: EventRepository,
    participant_repo: ParticipantRepository,
    clock: Clock,
    event: Event,
) -> tuple[Event, list[DomainEvent]]:
    if event.status == EventStatus.closed:
        return event, []
    now = clock.now()
    event.status = EventStatus.closed
    event.closed_at = now
    event.retention_until = now + timedelta(days=RETENTION_DAYS)
    event.updated_at = now
    await event_repo.update(event)
    await participant_repo.rotate_all_session_tokens(event.id)
    return event, [DomainEvent(type="event.closed", payload={"event_id": str(event.id)})]


async def join_via_qr(
    event_repo: EventRepository,
    participant_repo: ParticipantRepository,
    clock: Clock,
    *,
    join_code: str,
    pseudonym: str,
    noble_title: ParticipantNobleTitle | None,
    is_photographable: bool,
) -> tuple[Event, Participant]:
    now = clock.now()
    event = await event_repo.get_by_join_code(join_code)
    if event is None:
        raise NotFoundError("Serata non trovata.", code="event.not_found")
    if event.status in (EventStatus.closed, EventStatus.archived):
        raise EventClosedError("La serata è terminata.", code="event.closed")
    if event.status != EventStatus.open:
        raise ConflictError("La serata non è ancora aperta.", code="event.not_open")
    if not event.is_within_window(now):
        raise EventClosedError("La serata non è al momento in corso.", code="event.outside_window")

    existing = await participant_repo.get_by_pseudonym(event.id, pseudonym)
    if existing is not None:
        raise ConflictError(
            "Questo pseudonimo è già in uso in questa serata.",
            code="participant.pseudonym_taken",
            details={"field": "pseudonym"},
        )

    participant = Participant(
        id=uuid7(),
        event_id=event.id,
        pseudonym=pseudonym,
        noble_title=noble_title,
        role=ParticipantRole.guest,
        score=0,
        is_photographable=is_photographable,
        consent_at=now if is_photographable else None,
        consent_revoked_at=None,
        session_token_id=uuid7(),
        last_seen_at=None,
        left_at=None,
        created_at=now,
        updated_at=now,
    )
    await participant_repo.add(participant)
    return event, participant


async def set_consent(
    participant_repo: ParticipantRepository,
    clock: Clock,
    participant: Participant,
    *,
    is_photographable: bool,
) -> ConsentResult:
    now = clock.now()
    participant.is_photographable = is_photographable
    if is_photographable:
        participant.consent_at = now
        participant.consent_revoked_at = None
    else:
        participant.consent_revoked_at = now
    participant.updated_at = now
    await participant_repo.update(participant)

    event = DomainEvent(
        type="profile.consent_changed",
        payload={"participant_id": str(participant.id), "is_photographable": is_photographable},
        target_participant_id=participant.id,
    )
    return ConsentResult(participant=participant, events=[event])


async def leave_event(
    participant_repo: ParticipantRepository, clock: Clock, participant: Participant
) -> Participant:
    now = clock.now()
    participant.left_at = now
    participant.updated_at = now
    await participant_repo.update(participant)
    return participant


async def rotate_host_session(
    participant_repo: ParticipantRepository, clock: Clock, host: Participant
) -> Participant:
    host.session_token_id = uuid7()
    host.updated_at = clock.now()
    await participant_repo.update(host)
    return host
