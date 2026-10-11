from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints, field_validator

from src.storage.models import Profile
from src.timestamps import UtcDatetime

SkinType = Literal["dry", "normal", "combination", "oily"]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Amount = Annotated[
    Decimal,
    Field(ge=0, max_digits=10, decimal_places=2),
    PlainSerializer(float, return_type=float, when_used="json"),
]


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Amount
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class ProfileOut(BaseModel):
    user_id: UUID
    timezone: str
    goals: list[str]
    skin_type: SkinType | None
    concerns: list[str] | None
    ingredient_exclusions: list[str] | None
    budget: Budget | None
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @classmethod
    def from_profile(cls, profile: Profile) -> "ProfileOut":
        budget = None
        if profile.budget_amount is not None and profile.budget_currency is not None:
            budget = Budget(amount=profile.budget_amount, currency=profile.budget_currency)
        return cls(
            user_id=profile.user_id,
            timezone=profile.timezone,
            goals=profile.goals,
            skin_type=profile.skin_type,
            concerns=profile.concerns,
            ingredient_exclusions=profile.ingredient_exclusions,
            budget=budget,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )


class ProfileUpdate(BaseModel):
    """Only the fields sent are changed. `null` clears a nullable field."""

    # Rejects unknown fields, including any user_id sent by the browser.
    model_config = ConfigDict(extra="forbid")

    timezone: str | None = None
    goals: Annotated[list[ShortText], Field(max_length=10)] | None = None
    skin_type: SkinType | None = None
    concerns: Annotated[list[ShortText], Field(max_length=10)] | None = None
    # null means not answered; an empty list means the user reported none.
    ingredient_exclusions: Annotated[list[ShortText], Field(max_length=50)] | None = None
    budget: Budget | None = None

    @field_validator("timezone", "goals")
    @classmethod
    def required_when_sent(cls, value: object) -> object:
        if value is None:
            raise ValueError("may not be null")
        return value

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        if value not in available_timezones():
            raise ValueError("not an IANA timezone name")
        return value
