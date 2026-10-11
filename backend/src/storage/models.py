from dataclasses import dataclass, fields
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

# Fixed values shared by the API schemas, both stores, and the migration.
SKIN_TYPES = ("dry", "normal", "combination", "oily")
CONSENT_TYPES = ("service", "model_training", "photo_storage", "illustration")
INSIGHT_FEEDBACK = ("useful", "not_useful")

# Labels for the check-in scales. Stored values are the numbers.
#   mood:       1 low, 2 okay, 3 good, 4 great
#   connection: 1 quiet time, 2 a little, 3 connected
#   stress and sleep_quality: 1 (lowest) to 5 (highest)
CHECKIN_SCALE_VERSION = "checkin.v1"


@dataclass
class Profile:
    user_id: UUID
    timezone: str
    goals: list[str]
    skin_type: str | None
    concerns: list[str] | None
    ingredient_exclusions: list[str] | None
    budget_amount: Decimal | None
    budget_currency: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class Consent:
    id: UUID
    user_id: UUID
    consent_type: str
    version: str
    granted_at: datetime
    revoked_at: datetime | None


@dataclass
class CheckIn:
    id: UUID
    user_id: UUID
    local_date: date
    timezone: str
    scale_version: str
    sleep_hours: Decimal | None
    sleep_quality: int | None
    mood: int | None
    stress: int | None
    connection: int | None
    note: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class Insight:
    id: UUID
    user_id: UUID
    period_start: date
    period_end: date
    input_version: str
    rule_version: str
    text: str
    feedback: str | None
    feedback_at: datetime | None
    created_at: datetime


# The only columns a caller may change after a row exists.
PROFILE_EDITABLE = (
    "timezone", "goals", "skin_type", "concerns", "ingredient_exclusions",
    "budget_amount", "budget_currency",
)
CHECKIN_VALUES = ("sleep_hours", "sleep_quality", "mood", "stress", "connection", "note")


def column_names(model: type) -> tuple[str, ...]:
    return tuple(f.name for f in fields(model))
