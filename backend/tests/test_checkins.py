import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from tests.conftest import Actor

TODAY = datetime.now(timezone.utc).date()


def day(offset: int) -> str:
    return (TODAY - timedelta(days=offset)).isoformat()


def test_checkin_needs_service_consent(client: TestClient, new_user: Callable[[], uuid.UUID]) -> None:
    carol = Actor(client, new_user())
    refused = carol.post("/v1/checkins", json={"local_date": day(1), "mood": 3})
    assert refused.status_code == 403
    assert refused.json()["error"] == {
        "code": "consent_required",
        "message": "This needs your 'service' consent.",
        "consent_type": "service",
    }
    carol.consent()
    assert carol.post("/v1/checkins", json={"local_date": day(1), "mood": 3}).status_code == 201


def test_revoking_consent_stops_writes_but_not_reads(alice: Actor) -> None:
    created = alice.post("/v1/checkins", json={"local_date": day(1), "mood": 3}).json()
    alice.delete("/v1/consents/service")
    assert alice.post("/v1/checkins", json={"local_date": day(2), "mood": 2}).status_code == 403
    assert alice.patch(f"/v1/checkins/{created['id']}", json={"mood": 4}).status_code == 403
    assert [c["id"] for c in alice.get("/v1/checkins").json()["items"]] == [created["id"]]


def test_create_and_read_a_checkin(alice: Actor) -> None:
    alice.patch("/v1/me", json={"timezone": "America/New_York"})
    response = alice.post("/v1/checkins", json={
        "local_date": day(1), "sleep_hours": 7.5, "sleep_quality": 4, "mood": 3,
        "stress": 2, "connection": 3, "note": "  Slept well.  ",
    })
    assert response.status_code == 201
    checkin = response.json()
    assert checkin["local_date"] == day(1)
    assert checkin["sleep_hours"] == 7.5
    assert checkin["note"] == "Slept well."
    assert checkin["timezone"] == "America/New_York"
    assert checkin["scale_version"] == "checkin.v1"
    assert "user_id" not in checkin
    assert checkin["created_at"].endswith("Z") or checkin["created_at"].endswith("+00:00")
    assert alice.get("/v1/checkins").json()["items"] == [checkin]


def test_one_checkin_per_local_date(alice: Actor) -> None:
    first = alice.post("/v1/checkins", json={"local_date": day(1), "mood": 3}).json()
    duplicate = alice.post("/v1/checkins", json={"local_date": day(1), "mood": 1})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "checkin_exists"
    assert duplicate.json()["error"]["checkin_id"] == first["id"]
    assert alice.get("/v1/checkins").json()["items"][0]["mood"] == 3


def test_two_users_can_check_in_on_the_same_date(alice: Actor, bob: Actor) -> None:
    assert alice.post("/v1/checkins", json={"local_date": day(1), "mood": 3}).status_code == 201
    assert bob.post("/v1/checkins", json={"local_date": day(1), "mood": 1}).status_code == 201


def test_scale_values_and_ranges_are_validated(alice: Actor) -> None:
    invalid = [
        {"mood": 0}, {"mood": 5}, {"mood": "3"}, {"mood": 3.0}, {"mood": True},
        {"sleep_quality": 6}, {"stress": 0}, {"stress": 6}, {"connection": 4},
        {"sleep_hours": -0.5}, {"sleep_hours": 24.5}, {"sleep_hours": 7.25},
        {"note": "x" * 2001},
        {},
        {"note": "   "},
        {"mood": 3, "user_id": str(uuid.uuid4())},
        {"mood": 3, "energy": 5},
    ]
    for values in invalid:
        response = alice.post("/v1/checkins", json={"local_date": day(1), **values})
        assert response.status_code == 422, values
    assert alice.post("/v1/checkins", json={"mood": 3}).status_code == 422
    assert alice.post("/v1/checkins", json={"local_date": "yesterday", "mood": 3}).status_code == 422
    assert alice.get("/v1/checkins").json()["items"] == []


def test_boundary_values_are_accepted(alice: Actor) -> None:
    low = alice.post("/v1/checkins", json={
        "local_date": day(1), "sleep_hours": 0, "sleep_quality": 1, "mood": 1, "stress": 1, "connection": 1,
    })
    high = alice.post("/v1/checkins", json={
        "local_date": day(2), "sleep_hours": 24, "sleep_quality": 5, "mood": 4, "stress": 5, "connection": 3,
        "note": "x" * 2000,
    })
    assert low.status_code == 201 and high.status_code == 201
    assert low.json()["sleep_hours"] == 0.0 and high.json()["sleep_hours"] == 24.0


def test_validation_errors_do_not_echo_the_note(alice: Actor) -> None:
    response = alice.post("/v1/checkins", json={"local_date": day(1), "mood": 9, "note": "a private thought"})
    assert response.status_code == 422
    assert "a private thought" not in response.text
    assert response.json()["error"]["fields"][0]["field"] == "mood"


def test_future_dates_follow_the_users_timezone(alice: Actor) -> None:
    # Kiritimati is 14 hours ahead of UTC, so its "today" can be UTC's tomorrow.
    alice.patch("/v1/me", json={"timezone": "Pacific/Kiritimati"})
    local_today = datetime.now(ZoneInfo("Pacific/Kiritimati")).date()
    tomorrow = alice.post("/v1/checkins", json={"local_date": (local_today + timedelta(days=1)).isoformat(), "mood": 3})
    assert tomorrow.status_code == 422
    assert tomorrow.json()["error"]["code"] == "date_in_future"
    today = alice.post("/v1/checkins", json={"local_date": local_today.isoformat(), "mood": 3})
    assert today.status_code == 201
    assert today.json()["timezone"] == "Pacific/Kiritimati"


def test_edit_an_owned_checkin(alice: Actor) -> None:
    created = alice.post("/v1/checkins", json={"local_date": day(1), "mood": 2, "note": "tired"}).json()
    updated = alice.patch(f"/v1/checkins/{created['id']}", json={"mood": 4, "note": None, "sleep_hours": 8})
    assert updated.status_code == 200
    body = updated.json()
    assert (body["mood"], body["note"], body["sleep_hours"]) == (4, None, 8.0)
    assert body["local_date"] == created["local_date"]
    assert body["created_at"] == created["created_at"]
    assert body["updated_at"] >= created["updated_at"]

    assert alice.patch(f"/v1/checkins/{created['id']}", json={"mood": 9}).status_code == 422
    assert alice.patch(f"/v1/checkins/{created['id']}", json={"local_date": day(3)}).status_code == 422
    emptied = alice.patch(f"/v1/checkins/{created['id']}", json={"mood": None, "sleep_hours": None})
    assert emptied.status_code == 422 and emptied.json()["error"]["code"] == "empty_checkin"
    assert alice.get("/v1/checkins").json()["items"] == [body]


def test_users_cannot_reach_each_others_checkins(alice: Actor, bob: Actor) -> None:
    hers = alice.post("/v1/checkins", json={"local_date": day(1), "mood": 2, "note": "private"}).json()

    assert bob.patch(f"/v1/checkins/{hers['id']}", json={"mood": 4}).status_code == 404
    assert bob.patch(f"/v1/checkins/{uuid.uuid4()}", json={"mood": 4}).status_code == 404
    assert bob.get("/v1/checkins").json()["items"] == []
    # A user id supplied by the browser is never used to choose whose data to return.
    assert bob.get("/v1/checkins", params={"user_id": str(alice.id)}).json()["items"] == []
    assert alice.get("/v1/checkins").json()["items"] == [hers]


def test_history_is_filtered_by_date_range(alice: Actor) -> None:
    for offset in (1, 3, 5, 10):
        alice.post("/v1/checkins", json={"local_date": day(offset), "mood": 3})

    def dates(**params: str) -> list[str]:
        return [c["local_date"] for c in alice.get("/v1/checkins", params=params).json()["items"]]

    assert dates() == [day(1), day(3), day(5), day(10)]
    assert dates(**{"from": day(5), "to": day(3)}) == [day(3), day(5)]
    assert dates(**{"from": day(4)}) == [day(1), day(3)]
    assert dates(to=day(6)) == [day(10)]
    assert alice.get("/v1/checkins", params={"from": day(1), "to": day(5)}).status_code == 422
    assert alice.get("/v1/checkins", params={"from": "soon"}).status_code == 422


def test_backdated_checkin_keeps_its_date(alice: Actor) -> None:
    old = date(2026, 1, 15).isoformat()
    assert alice.post("/v1/checkins", json={"local_date": old, "mood": 3}).json()["local_date"] == old
