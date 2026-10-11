from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.timestamps import today_in


def test_today_follows_the_named_timezone() -> None:
    assert today_in("Pacific/Kiritimati") == datetime.now(ZoneInfo("Pacific/Kiritimati")).date()


def test_unreadable_timezone_falls_back_to_utc() -> None:
    utc_today = datetime.now(timezone.utc).date()
    assert today_in("Mars/Olympus_Mons") == utc_today
    assert today_in("../etc/passwd") == utc_today
