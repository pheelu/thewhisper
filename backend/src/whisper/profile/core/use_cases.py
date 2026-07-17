"""Use case del profilo: creazione/aggiornamento con accredito `profile_completed`."""

from uuid import UUID

from whisper.profile.core.entities import Profile
from whisper.profile.core.enums import ProfileRevealStage
from whisper.profile.core.repositories import ProfileRepository
from whisper.shared.core.clock import Clock
from whisper.shared.core.enums import PointReason
from whisper.shared.core.events import DomainEvent
from whisper.shared.core.ids import uuid7
from whisper.shared.core.ports import PointsPort

PROFILE_COMPLETED_POINTS = 5


async def upsert_profile(
    repo: ProfileRepository,
    points: PointsPort,
    clock: Clock,
    *,
    event_id: UUID,
    participant_id: UUID,
    secret_text: str | None,
    motto: str | None,
    accent_color: str | None,
    avatar_seed: str | None,
) -> tuple[Profile, list[DomainEvent]]:
    now = clock.now()
    profile = await repo.get_by_participant(event_id, participant_id)
    was_complete = profile.is_complete if profile else False

    if profile is None:
        profile = Profile(
            id=uuid7(),
            event_id=event_id,
            participant_id=participant_id,
            secret_text=secret_text,
            motto=motto,
            avatar_seed=avatar_seed or participant_id.hex[:12],
            accent_color=accent_color,
            clues=[],
            reveal_stage=ProfileRevealStage.concealed,
            is_complete=False,
            completed_at=None,
            disclosed_publicly_at=None,
            created_at=now,
            updated_at=now,
        )
        created = True
    else:
        # merge: aggiorna solo i campi forniti (None = invariato)
        if secret_text is not None:
            profile.secret_text = secret_text
        if motto is not None:
            profile.motto = motto
        if accent_color is not None:
            profile.accent_color = accent_color
        if avatar_seed is not None:
            profile.avatar_seed = avatar_seed
        profile.updated_at = now
        created = False

    newly_complete = not was_complete and profile.compute_complete()
    if newly_complete:
        profile.is_complete = True
        profile.completed_at = now

    if created:
        await repo.add(profile)
    else:
        await repo.update(profile)

    events: list[DomainEvent] = [
        DomainEvent(
            type="profile.updated",
            payload={
                "participant_id": str(participant_id),
                "motto": profile.motto,
                "accent_color": profile.accent_color,
                "avatar_seed": profile.avatar_seed,
            },
        )
    ]

    if newly_complete:
        result = await points.award_points(
            event_id=event_id,
            participant_id=participant_id,
            delta=PROFILE_COMPLETED_POINTS,
            reason=PointReason.profile_completed,
            source_domain="profile",
            idempotency_key=f"profile_completed:{participant_id}",
        )
        events.extend(result.events)

    return profile, events
