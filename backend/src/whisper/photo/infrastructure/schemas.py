"""Schemi Pydantic delle Foto Whisper."""

from uuid import UUID

from pydantic import BaseModel, Field


class CreateDraftRequest(BaseModel):
    subject_participant_id: UUID
    mysterious_title: str = Field(min_length=1, max_length=120)
    content_type: str = "image/jpeg"


class CreateDraftResponse(BaseModel):
    photo_id: UUID
    upload_url: str
    content_type: str
