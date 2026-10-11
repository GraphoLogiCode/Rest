from datetime import date, datetime, timezone
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return value.astimezone(timezone.utc)


# Timestamps leave the API in UTC whatever timezone the database session uses.
UtcDatetime = Annotated[datetime, AfterValidator(_to_utc)]


def today_in(timezone_name: str) -> date:
    """Today's date where the user is. An unreadable stored timezone falls back to UTC."""
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return datetime.now(zone).date()
