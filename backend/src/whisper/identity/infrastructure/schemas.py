"""Schemi Pydantic (request/response) del dominio identity."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from whisper.identity.core.entities import Event, Participant
from whisper.shared.core.enums import EventStatus, ParticipantNobleTitle, ParticipantRole


# ---------- Request ----------
class CreateEventRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    venue_name: str | None = Field(default=None, max_length=120)
    starts_at: datetime
    ends_at: datetime
    timezone: str = "Europe/Rome"
    host_secret: str = Field(min_length=4, max_length=128)
    host_pseudonym: str = Field(default="Padrone di Casa", min_length=1, max_length=40)


class HostSessionRequest(BaseModel):
    host_secret: str = Field(min_length=1, max_length=128)


class JoinRequest(BaseModel):
    join_code: str = Field(min_length=4, max_length=32)
    pseudonym: str = Field(min_length=1, max_length=40)
    noble_title: ParticipantNobleTitle | None = None
    is_photographable: bool = False


class ConsentRequest(BaseModel):
    is_photographable: bool


# ---------- Response ----------
class EventPublic(BaseModel):
    id: UUID
    name: str
    venue_name: str | None
    status: EventStatus
    starts_at: datetime
    ends_at: datetime
    timezone: str


class EventHostView(EventPublic):
    join_code: str


class ParticipantPublic(BaseModel):
    id: UUID
    pseudonym: str
    noble_title: ParticipantNobleTitle | None
    role: ParticipantRole
    score: int
    is_photographable: bool


class MeResponse(BaseModel):
    participant: ParticipantPublic
    event: EventPublic


class JoinResponse(BaseModel):
    participant: ParticipantPublic
    event: EventPublic


class CreateEventResponse(BaseModel):
    event: EventHostView
    host: ParticipantPublic
    host_token: str
    join_url: str


class HostSessionResponse(BaseModel):
    event: EventHostView
    host_token: str


# ---------- Mapping entità → schema ----------
def event_public(event: Event) -> EventPublic:
    return EventPublic(
        id=event.id,
        name=event.name,
        venue_name=event.venue_name,
        status=event.status,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        timezone=event.timezone,
    )


def event_host_view(event: Event) -> EventHostView:
    return EventHostView(**event_public(event).model_dump(), join_code=event.join_code)


def participant_public(participant: Participant) -> ParticipantPublic:
    return ParticipantPublic(
        id=participant.id,
        pseudonym=participant.pseudonym,
        noble_title=participant.noble_title,
        role=participant.role,
        score=participant.score,
        is_photographable=participant.is_photographable,
    )
