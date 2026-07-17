"""Schemi Pydantic della scoperta."""

from uuid import UUID

from pydantic import BaseModel, Field


class CommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=500)


class GuessRequest(BaseModel):
    guessed_subject_participant_id: UUID


class GuessResponse(BaseModel):
    is_correct: bool
    guess_rank: int | None
    points_awarded: int
    attempts_left: int
