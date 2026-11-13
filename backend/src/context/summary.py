"""Descriptive summaries of a user's check-ins.

A summary reports what was logged and how complete the record is. It never
says why something changed: check-ins alone cannot separate lifestyle effects
from product effects.
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from src.storage.models import CheckIn

RULE_VERSION = "summary.v1"
PERIOD_DAYS = {"week": 7, "month": 30}
# Fewer sleep entries than this are counted but not averaged.
MIN_VALUES_FOR_AVERAGE = 3
SCALE_RANGES = {"sleep_quality": (1, 5), "mood": (1, 4), "stress": (1, 5), "connection": (1, 3)}
LIMITATION = "This describes what you logged. It does not explain what caused any change."


def period_bounds(period: str, today: date) -> tuple[date, date]:
    """The period ends today and includes it."""
    return today - timedelta(days=PERIOD_DAYS[period] - 1), today


def _one_decimal(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def summarize(checkins: Sequence[CheckIn], start: date, end: date) -> dict[str, Any]:
    days = (end - start).days + 1
    sleep = [c.sleep_hours for c in checkins if c.sleep_hours is not None]
    enough_sleep = len(sleep) >= MIN_VALUES_FOR_AVERAGE

    scales: dict[str, Any] = {}
    for name, (low, high) in SCALE_RANGES.items():
        values = [getattr(c, name) for c in checkins if getattr(c, name) is not None]
        scales[name] = {
            "count": len(values),
            "counts": {str(level): values.count(level) for level in range(low, high + 1)},
        }

    return {
        "coverage": {
            "days": days,
            "days_with_checkin": len({c.local_date for c in checkins}),
            "notes": sum(1 for c in checkins if c.note),
        },
        "sleep_hours": {
            "count": len(sleep),
            "mean": _one_decimal(sum(sleep, Decimal(0)) / len(sleep)) if enough_sleep else None,
            "min": float(min(sleep)) if enough_sleep else None,
            "max": float(max(sleep)) if enough_sleep else None,
        },
        "scales": scales,
    }


def input_version(checkins: Sequence[CheckIn], start: date, end: date) -> str:
    """Identifies exactly which values a summary was computed from. Notes are not used."""
    rows = sorted(
        [c.local_date.isoformat(), str(c.sleep_hours), c.sleep_quality, c.mood, c.stress, c.connection]
        for c in checkins
    )
    payload = json.dumps([start.isoformat(), end.isoformat(), rows], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def insight_text(summary: dict[str, Any]) -> str:
    """Fixed wording only. Every sentence states a count or an average of logged values."""
    coverage = summary["coverage"]
    if coverage["days_with_checkin"] == 0:
        return f"No check-ins are recorded for the last {coverage['days']} days."
    sentences = [f"You checked in on {coverage['days_with_checkin']} of the last {coverage['days']} days."]
    sleep = summary["sleep_hours"]
    if sleep["mean"] is not None:
        sentences.append(f"Your logged sleep averaged {sleep['mean']:.1f} hours a night.")
    elif sleep["count"]:
        sentences.append("There are too few sleep entries to average.")
    sentences.append(LIMITATION)
    return " ".join(sentences)
