import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from src.context.summary import LIMITATION, input_version, insight_text, period_bounds, summarize
from src.storage.models import CheckIn
from tests.conftest import Actor

TODAY = datetime.now(timezone.utc).date()


def day(offset: int) -> str:
    return (TODAY - timedelta(days=offset)).isoformat()


def log(actor: Actor, offset: int, **values: object) -> dict:
    response = actor.post("/v1/checkins", json={"local_date": day(offset), **values})
    assert response.status_code == 201, response.text
    return response.json()


def test_empty_week_reports_no_data(alice: Actor) -> None:
    summary = alice.get("/v1/summary").json()
    assert summary["period"] == "week"
    assert (summary["period_start"], summary["period_end"]) == (day(6), day(0))
    assert summary["coverage"] == {"days": 7, "days_with_checkin": 0, "notes": 0}
    assert summary["sleep_hours"] == {"count": 0, "mean": None, "min": None, "max": None}
    assert summary["scales"]["mood"] == {"count": 0, "counts": {"1": 0, "2": 0, "3": 0, "4": 0}}
    assert summary["insight"]["text"] == "No check-ins are recorded for the last 7 days."


def test_week_summary_describes_what_was_logged(alice: Actor) -> None:
    log(alice, 0, sleep_hours=7, mood=3, note="ok")
    log(alice, 1, sleep_hours=8, mood=3, stress=2)
    log(alice, 2, sleep_hours=6.5, mood=1)
    log(alice, 3, connection=2)
    log(alice, 9, sleep_hours=2, mood=4)  # outside the week

    summary = alice.get("/v1/summary", params={"period": "week"}).json()
    assert summary["coverage"] == {"days": 7, "days_with_checkin": 4, "notes": 1}
    assert summary["sleep_hours"] == {"count": 3, "mean": 7.2, "min": 6.5, "max": 8.0}
    assert summary["scales"]["mood"] == {"count": 3, "counts": {"1": 1, "2": 0, "3": 2, "4": 0}}
    assert summary["scales"]["stress"]["count"] == 1
    assert summary["scales"]["connection"]["counts"] == {"1": 0, "2": 1, "3": 0}
    assert summary["insight"]["text"] == (
        "You checked in on 4 of the last 7 days. Your logged sleep averaged 7.2 hours a night. " + LIMITATION
    )
    assert summary["insight"]["rule_version"] == "summary.v1"

    month = alice.get("/v1/summary", params={"period": "month"}).json()
    assert month["coverage"]["days"] == 30 and month["coverage"]["days_with_checkin"] == 5
    assert alice.get("/v1/summary", params={"period": "year"}).status_code == 422


def test_too_few_sleep_entries_are_not_averaged(alice: Actor) -> None:
    log(alice, 0, sleep_hours=4)
    log(alice, 1, sleep_hours=9)
    summary = alice.get("/v1/summary").json()
    assert summary["sleep_hours"] == {"count": 2, "mean": None, "min": None, "max": None}
    assert "too few sleep entries" in summary["insight"]["text"]
    assert "averaged" not in summary["insight"]["text"]


def test_insight_is_stable_until_the_inputs_change(alice: Actor) -> None:
    created = log(alice, 0, mood=2)
    first = alice.get("/v1/summary").json()["insight"]
    assert alice.get("/v1/summary").json()["insight"]["id"] == first["id"]

    alice.patch(f"/v1/checkins/{created['id']}", json={"mood": 4})
    changed = alice.get("/v1/summary").json()["insight"]
    assert changed["id"] != first["id"] and changed["input_version"] != first["input_version"]


def test_feedback_is_recorded_on_an_owned_insight(alice: Actor, bob: Actor) -> None:
    log(alice, 0, mood=3)
    insight = alice.get("/v1/summary").json()["insight"]
    assert insight["feedback"] is None

    assert bob.post(f"/v1/insights/{insight['id']}/feedback", json={"feedback": "useful"}).status_code == 404
    assert alice.post(f"/v1/insights/{uuid.uuid4()}/feedback", json={"feedback": "useful"}).status_code == 404
    assert alice.post(f"/v1/insights/{insight['id']}/feedback", json={"feedback": "great"}).status_code == 422

    saved = alice.post(f"/v1/insights/{insight['id']}/feedback", json={"feedback": "not_useful"})
    assert saved.status_code == 200
    assert saved.json()["feedback"] == "not_useful" and saved.json()["feedback_at"] is not None
    assert alice.get("/v1/summary").json()["insight"]["feedback"] == "not_useful"


def test_summary_only_counts_the_callers_checkins(alice: Actor, bob: Actor) -> None:
    log(alice, 0, mood=1)
    log(alice, 1, mood=1)
    assert bob.get("/v1/summary").json()["coverage"]["days_with_checkin"] == 0


def test_export_returns_everything_the_caller_owns_and_nothing_else(alice: Actor, bob: Actor) -> None:
    alice.patch("/v1/me", json={"goals": ["Sleep earlier"]})
    mine = log(alice, 1, mood=3, note="mine")
    log(bob, 1, mood=1, note="bob-only-note")
    alice.get("/v1/summary")

    response = alice.post("/v1/export")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    export = response.json()
    assert export["profile"]["user_id"] == str(alice.id)
    assert export["profile"]["goals"] == ["Sleep earlier"]
    assert export["checkins"] == [mine]
    assert [c["consent_type"] for c in export["consents"]] == ["service"]
    assert len(export["insights"]) == 1
    assert "bob-only-note" not in response.text and str(bob.id) not in response.text


def test_deleting_an_account_removes_only_the_callers_data(alice: Actor, bob: Actor) -> None:
    log(alice, 1, mood=3)
    log(alice, 2, mood=2)
    alice.get("/v1/summary")
    his = log(bob, 1, mood=1)

    deleted = alice.delete("/v1/account")
    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted": {"insights": 1, "checkins": 2, "consents": 1, "profiles": 1, "routine_state": 0, "progress_records": 0},
        "auth_identity_deleted": False,
    }
    assert alice.get("/v1/checkins").json()["items"] == []
    assert alice.get("/v1/consents").json()["items"] == []
    assert alice.post("/v1/export").json()["insights"] == []
    assert bob.get("/v1/checkins").json()["items"] == [his]
    assert len(bob.get("/v1/consents").json()["items"]) == 1


def test_every_response_is_marked_uncacheable(alice: Actor) -> None:
    assert alice.get("/v1/me").headers["Cache-Control"] == "no-store"
    assert alice.client.get("/v1/me").headers["Cache-Control"] == "no-store"


# The summary rules on their own.


def checkin(local_date: date, **values: object) -> CheckIn:
    base = dict(sleep_hours=None, sleep_quality=None, mood=None, stress=None, connection=None, note=None)
    base.update(values)
    now = datetime.now(timezone.utc)
    return CheckIn(id=uuid.uuid4(), user_id=uuid.uuid4(), local_date=local_date, timezone="UTC",
                   scale_version="checkin.v1", created_at=now, updated_at=now, **base)


def test_period_includes_today() -> None:
    assert period_bounds("week", date(2026, 10, 11)) == (date(2026, 10, 5), date(2026, 10, 11))
    assert period_bounds("month", date(2026, 10, 11)) == (date(2026, 9, 12), date(2026, 10, 11))


def test_mean_is_rounded_half_up_to_one_decimal() -> None:
    start, end = date(2026, 10, 5), date(2026, 10, 11)
    rows = [checkin(date(2026, 10, d), sleep_hours=Decimal(h)) for d, h in ((5, "7.0"), (6, "7.5"), (7, "7.5"), (8, "7.6"))]
    assert summarize(rows, start, end)["sleep_hours"]["mean"] == 7.4
    rows = [checkin(date(2026, 10, d), sleep_hours=Decimal(h)) for d, h in ((5, "7.0"), (6, "7.1"), (7, "7.1"), (8, "7.0"))]
    assert summarize(rows, start, end)["sleep_hours"]["mean"] == 7.1


def test_input_version_ignores_notes_and_order() -> None:
    start, end = date(2026, 10, 5), date(2026, 10, 11)
    a = checkin(date(2026, 10, 6), mood=3, note="first")
    b = checkin(date(2026, 10, 7), sleep_hours=Decimal("7.5"))
    assert input_version([a, b], start, end) == input_version([b, checkin(a.local_date, mood=3, note="edited")], start, end)
    assert input_version([a, b], start, end) != input_version([a], start, end)
    assert input_version([a, b], start, end) != input_version([a, b], start, date(2026, 10, 12))


def test_insight_never_explains_a_cause() -> None:
    start, end = date(2026, 10, 5), date(2026, 10, 11)
    rows = [checkin(date(2026, 10, d), sleep_hours=Decimal("4.0"), stress=5, mood=1) for d in (5, 6, 7, 8)]
    text = insight_text(summarize(rows, start, end))
    assert text.endswith(LIMITATION)
    for word in ("because", "caused by", "due to", "leads to", "skin"):
        assert word not in text.lower()
