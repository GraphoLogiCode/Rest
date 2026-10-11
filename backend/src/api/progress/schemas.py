from datetime import date, timedelta
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class DatedRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    entry_id: UUID


class UsageReport(DatedRecord):
    package_matches: Literal[True]
    product_id: str = Field(min_length=1, max_length=100)
    started_on: date
    ended_on: date
    used_days: int = Field(ge=0, le=3650, strict=True)
    helpfulness: Literal['unknown', 'helpful', 'no_change', 'unhelpful']
    irritation: Literal['unknown', 'none', 'mild', 'moderate', 'severe']
    stopped: StrictBool = False
    routine_changes: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def dates_and_use(self):
        if self.ended_on < self.started_on or self.ended_on > date.today() + timedelta(days=1):
            raise ValueError('Use a completed date interval')
        if (self.ended_on-self.started_on).days > 3650:
            raise ValueError('Interval must be within ten years')
        if self.used_days > (self.ended_on-self.started_on).days + 1:
            raise ValueError('Use days exceed the date interval')
        if self.used_days == 0 and (self.helpfulness != 'unknown' or self.irritation != 'unknown'):
            raise ValueError('An unused product cannot have a use outcome')
        return self


class PhotoRecord(DatedRecord):
    captured_on: date
    confirmed_real: Literal[True]
    view: Literal['front', 'left', 'right']
    lighting: Literal['daylight', 'indoor', 'mixed', 'unknown']
    makeup: StrictBool | None = None
    product_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode='after')
    def date_not_future(self):
        if self.captured_on > date.today() + timedelta(days=1):
            raise ValueError('Photo date cannot be in the future')
        return self


class Comparison(BaseModel):
    model_config = ConfigDict(extra='forbid')
    before_id: UUID
    after_id: UUID


class RecommendationFeedback(DatedRecord):
    recommendation_id: UUID
    product_id: str = Field(min_length=1, max_length=100)
    useful: StrictBool
    reason: Literal['fits_preferences', 'price', 'ingredients', 'unclear', 'other']
