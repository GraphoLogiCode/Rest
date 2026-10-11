from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from src.storage.models import CHECKIN_VALUES
from src.timestamps import UtcDatetime

Hours = Annotated[
    Decimal,
    Field(ge=0, le=24, max_digits=3, decimal_places=1),
    PlainSerializer(float, return_type=float, when_used="json"),
]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class CheckInValues(BaseModel):
    """Every value is optional. Scales are whole numbers; see CHECKIN_SCALE_VERSION."""

    # Rejects unknown fields, including any user_id sent by the browser.
    model_config = ConfigDict(extra="forbid")

    sleep_hours: Hours | None = None
    sleep_quality: Annotated[StrictInt, Field(ge=1, le=5)] | None = None
    mood: Annotated[StrictInt, Field(ge=1, le=4)] | None = None
    stress: Annotated[StrictInt, Field(ge=1, le=5)] | None = None
    connection: Annotated[StrictInt, Field(ge=1, le=3)] | None = None
    note: Note | None = None

    @field_validator("note")
    @classmethod
    def blank_note_is_none(cls, value: str | None) -> str | None:
        return value or None


class CheckInCreate(CheckInValues):
    local_date: date

    @model_validator(mode="after")
    def has_a_value(self) -> "CheckInCreate":
        if all(getattr(self, name) is None for name in CHECKIN_VALUES):
            raise ValueError("a check-in needs at least one value")
        return self


class CheckInUpdate(CheckInValues):
    """Only the fields sent are changed. `null` clears a value. The date cannot change."""


class CheckInOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    local_date: date
    timezone: str
    scale_version: str
    sleep_hours: Hours | None
    sleep_quality: int | None
    mood: int | None
    stress: int | None
    connection: int | None
    note: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class CheckInList(BaseModel):
    items: list[CheckInOut]
