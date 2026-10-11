from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.timestamps import UtcDatetime

Period = Literal["week", "month"]
Feedback = Literal["useful", "not_useful"]


class InsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    period_start: date
    period_end: date
    input_version: str
    rule_version: str
    text: str
    feedback: Feedback | None
    feedback_at: UtcDatetime | None
    created_at: UtcDatetime


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: Feedback


class Coverage(BaseModel):
    days: int
    days_with_checkin: int
    notes: int


class SleepSummary(BaseModel):
    count: int
    # null until there are enough entries to average.
    mean: float | None
    min: float | None
    max: float | None


class ScaleSummary(BaseModel):
    count: int
    counts: dict[str, int]


class SummaryOut(BaseModel):
    period: Period
    period_start: date
    period_end: date
    timezone: str
    coverage: Coverage
    sleep_hours: SleepSummary
    scales: dict[str, ScaleSummary]
    insight: InsightOut
