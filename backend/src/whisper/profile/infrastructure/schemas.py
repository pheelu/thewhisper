"""Schemi Pydantic del profilo."""

from uuid import UUID

from pydantic import BaseModel, Field

from whisper.profile.core.entities import Profile
from whisper.profile.core.enums import ProfileRevealStage


class UpdateProfileRequest(BaseModel):
    secret_text: str | None = Field(default=None, max_length=280)
    motto: str | None = Field(default=None, max_length=140)
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    avatar_seed: str | None = Field(default=None, max_length=64)


class ProfileMe(BaseModel):
    participant_id: UUID
    secret_text: str | None
    motto: str | None
    avatar_seed: str
    accent_color: str | None
    reveal_stage: ProfileRevealStage
    is_complete: bool


def profile_me(profile: Profile) -> ProfileMe:
    return ProfileMe(
        participant_id=profile.participant_id,
        secret_text=profile.secret_text,
        motto=profile.motto,
        avatar_seed=profile.avatar_seed,
        accent_color=profile.accent_color,
        reveal_stage=profile.reveal_stage,
        is_complete=profile.is_complete,
    )


def empty_profile_me(participant_id: UUID) -> ProfileMe:
    return ProfileMe(
        participant_id=participant_id,
        secret_text=None,
        motto=None,
        avatar_seed=participant_id.hex[:12],
        accent_color=None,
        reveal_stage=ProfileRevealStage.concealed,
        is_complete=False,
    )
