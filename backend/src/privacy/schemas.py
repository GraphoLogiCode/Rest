from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

from src.api.checkins.schemas import CheckInOut
from src.api.routine.schemas import RoutineDocument
from src.api.profile.schemas import ProfileOut
from src.context.schemas import InsightOut
from src.timestamps import UtcDatetime

ConsentType = Literal["service", "model_training", "photo_storage", "illustration"]


class ConsentGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The version of the notice the user agreed to.
    version: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._-]{1,40}$")]


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    consent_type: ConsentType
    version: str
    granted_at: UtcDatetime
    revoked_at: UtcDatetime | None

    @computed_field
    @property
    def active(self) -> bool:
        return self.revoked_at is None


class ConsentList(BaseModel):
    items: list[ConsentOut]


class ExportOut(BaseModel):
    exported_at: UtcDatetime
    profile: ProfileOut
    consents: list[ConsentOut]
    checkins: list[CheckInOut]
    insights: list[InsightOut]
    routine: RoutineDocument
    illustration_jobs: list[dict] = Field(default_factory=list)
    illustration_usage: list[dict] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)
    recommendation_feedback: list[dict] = Field(default_factory=list)
    usage_reports: list[dict] = Field(default_factory=list)
    photos: list[dict] = Field(default_factory=list)


class AccountDeleted(BaseModel):
    deleted: dict[str, int]
    # Removing the sign-in identity needs Supabase's admin API and is not done here.
    auth_identity_deleted: bool
