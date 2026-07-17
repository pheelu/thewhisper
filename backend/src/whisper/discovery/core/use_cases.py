"""Use case della scoperta: commenti e guess con scoring (§5 del documento)."""

from dataclasses import dataclass, field
from uuid import UUID

from whisper.discovery.core.entities import Comment, Guess
from whisper.discovery.core.enums import CommentStatus
from whisper.discovery.core.repositories import DiscoveryRepository
from whisper.photo.core.enums import PhotoStatus
from whisper.photo.core.ports import PhotoPort
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

GUESS_POINTS_BY_RANK = {1: 25, 2: 20, 3: 15}
DEFAULT_GUESS_POINTS = 10
PHOTO_SOLVED_POINTS = 20
HUNTER_BONUS_POINTS = 3
HUNTER_BONUS_CAP = 10
MAX_ATTEMPTS = 3


@dataclass
class GuessOutcome:
    is_correct: bool
    guess_rank: int | None
    points_awarded: int
    attempts_left: int
    events: list[DomainEvent] = field(default_factory=list)


async def _published_context(photo_port: PhotoPort, event_id: UUID, photo_id: UUID):
    ctx = await photo_port.get_context(event_id, photo_id)
    if ctx is None:
        raise NotFoundError("Foto non trovata.", code="photo.not_found")
    if ctx.status != PhotoStatus.published:
        raise ConflictError("La foto non è nel feed.", code="photo.not_published")
    return ctx


async def add_comment(
    repo: DiscoveryRepository,
    photo_port: PhotoPort,
    clock: Clock,
    *,
    event_id: UUID,
    photo_id: UUID,
    author_id: UUID,
    body: str,
) -> tuple[Comment, list[DomainEvent]]:
    await _published_context(photo_port, event_id, photo_id)
    now = clock.now()
    comment = Comment(
        id=uuid7(),
        event_id=event_id,
        photo_id=photo_id,
        author_participant_id=author_id,
        body=body,
        status=CommentStatus.visible,
        created_at=now,
    )
    await repo.add_comment(comment)
    comment_count = await photo_port.bump_comment_count(photo_id, 1)

    event = DomainEvent(
        type="discovery.comment_added",
        payload={
            "photo_id": str(photo_id),
            "comment_id": str(comment.id),
            "author_participant_id": str(author_id),
            "body": body,
            "created_at": now.isoformat(),
            "comment_count": comment_count,
        },
    )
    return comment, [event]


async def submit_guess(
    repo: DiscoveryRepository,
    photo_port: PhotoPort,
    points: PointsPort,
    clock: Clock,
    *,
    event_id: UUID,
    photo_id: UUID,
    guesser_id: UUID,
    candidate_id: UUID,
) -> GuessOutcome:
    ctx = await _published_context(photo_port, event_id, photo_id)

    if guesser_id in (ctx.hunter_participant_id, ctx.subject_participant_id):
        raise ForbiddenError("Conosci già la risposta.", code="discovery.insider")
    if not await repo.candidate_is_guest(event_id, candidate_id):
        raise ValidationError("Candidato non valido.", code="discovery.bad_candidate")
    if await repo.has_correct_by(photo_id, guesser_id):
        raise ConflictError("Hai già indovinato questa foto.", code="discovery.already_correct")
    if await repo.has_guessed_candidate(photo_id, guesser_id, candidate_id):
        raise ConflictError("Hai già proposto questo nome.", code="discovery.duplicate_guess")
    attempts = await repo.attempts_by(photo_id, guesser_id)
    if attempts >= MAX_ATTEMPTS:
        raise ConflictError("Hai esaurito i tentativi.", code="discovery.no_attempts_left")

    now = clock.now()
    is_correct = candidate_id == ctx.subject_participant_id
    attempts_left = MAX_ATTEMPTS - (attempts + 1)
    events: list[DomainEvent] = []
    rank: int | None = None
    points_awarded = 0

    await repo.add_guess(
        Guess(
            id=uuid7(),
            event_id=event_id,
            photo_id=photo_id,
            guesser_participant_id=guesser_id,
            guessed_subject_participant_id=candidate_id,
            is_correct=is_correct,
            guess_rank=None,
            created_at=now,
        )
    )
    await repo.upsert_state(
        event_id=event_id, photo_id=photo_id, is_correct=is_correct, guesser_id=guesser_id, now=now
    )

    if is_correct:
        rank = await repo.distinct_correct_guessers(photo_id)
        points_awarded = GUESS_POINTS_BY_RANK.get(rank, DEFAULT_GUESS_POINTS)
        meta = {"photo_id": str(photo_id)}

        r_guesser = await points.award_points(
            event_id=event_id,
            participant_id=guesser_id,
            delta=points_awarded,
            reason=PointReason.subject_guessed,
            source_domain="discovery",
            idempotency_key=f"subject_guessed:{photo_id}:{guesser_id}",
            metadata=meta,
        )
        events.extend(r_guesser.events)

        r_solved = await points.award_points(
            event_id=event_id,
            participant_id=ctx.hunter_participant_id,
            delta=PHOTO_SOLVED_POINTS,
            reason=PointReason.photo_solved,
            source_domain="discovery",
            idempotency_key=f"photo_solved:{photo_id}",
            metadata=meta,
        )
        events.extend(r_solved.events)

        if rank <= HUNTER_BONUS_CAP:
            r_bonus = await points.award_points(
                event_id=event_id,
                participant_id=ctx.hunter_participant_id,
                delta=HUNTER_BONUS_POINTS,
                reason=PointReason.hunter_guess_bonus,
                source_domain="discovery",
                idempotency_key=f"hunter_guess_bonus:{photo_id}:{guesser_id}",
                metadata=meta,
            )
            events.extend(r_bonus.events)

        correct_count = await photo_port.bump_correct_guess_count(photo_id, 1)

        if rank == 1:
            events.append(
                DomainEvent(
                    type="discovery.photo_solved",
                    payload={
                        "photo_id": str(photo_id),
                        "solved_at": now.isoformat(),
                        "correct_guess_count": correct_count,
                    },
                )
            )
        for target in (ctx.hunter_participant_id, ctx.subject_participant_id):
            events.append(
                DomainEvent(
                    type="discovery.subject_guessed",
                    payload={
                        "photo_id": str(photo_id),
                        "correct_guess_count": correct_count,
                        "latest_guess_rank": rank,
                    },
                    target_participant_id=target,
                )
            )

    events.append(
        DomainEvent(
            type="discovery.guess_result",
            payload={
                "photo_id": str(photo_id),
                "is_correct": is_correct,
                "guess_rank": rank,
                "points_awarded": points_awarded,
                "attempts_left": attempts_left,
            },
            target_participant_id=guesser_id,
        )
    )
    return GuessOutcome(
        is_correct=is_correct,
        guess_rank=rank,
        points_awarded=points_awarded,
        attempts_left=attempts_left,
        events=events,
    )
