from tests.conftest import Actor


def test_profile_is_created_with_defaults(alice: Actor) -> None:
    profile = alice.get("/v1/me").json()
    assert profile["user_id"] == str(alice.id)
    assert profile["timezone"] == "UTC"
    assert profile["goals"] == []
    # Not answered is different from "none".
    assert profile["ingredient_exclusions"] is None
    assert profile["budget"] is None


def test_profile_update_changes_only_what_is_sent(alice: Actor) -> None:
    first = alice.patch("/v1/me", json={
        "timezone": "America/New_York",
        "goals": ["  Find a simple moisturizer  "],
        "skin_type": "dry",
        "ingredient_exclusions": [],
        "budget": {"amount": 20, "currency": "USD"},
    })
    assert first.status_code == 200
    assert first.json()["goals"] == ["Find a simple moisturizer"]
    assert first.json()["ingredient_exclusions"] == []
    assert first.json()["budget"] == {"amount": 20.0, "currency": "USD"}

    second = alice.patch("/v1/me", json={"skin_type": None, "budget": None}).json()
    assert second["timezone"] == "America/New_York"
    assert second["goals"] == ["Find a simple moisturizer"]
    assert second["skin_type"] is None
    assert second["budget"] is None
    assert alice.get("/v1/me").json() == second


def test_profile_rejects_invalid_values(alice: Actor) -> None:
    invalid = [
        {"timezone": "Mars/Olympus_Mons"},
        {"timezone": None},
        {"goals": None},
        {"goals": [""]},
        {"goals": ["x"] * 11},
        {"skin_type": "glowing"},
        {"budget": {"amount": -1, "currency": "USD"}},
        {"budget": {"amount": 10.999, "currency": "USD"}},
        {"budget": {"amount": 10, "currency": "usd"}},
        {"budget": {"amount": 10}},
        {"user_id": "00000000-0000-0000-0000-000000000000"},
        {"created_at": "2020-01-01T00:00:00Z"},
    ]
    for body in invalid:
        response = alice.patch("/v1/me", json=body)
        assert response.status_code == 422, body
        assert response.json()["error"]["code"] == "validation_error"
    assert alice.get("/v1/me").json()["timezone"] == "UTC"


def test_profiles_are_separate(alice: Actor, bob: Actor) -> None:
    alice.patch("/v1/me", json={"goals": ["Sleep earlier"]})
    assert bob.get("/v1/me").json()["goals"] == []
    assert bob.get("/v1/me").json()["user_id"] == str(bob.id)


def test_consent_history_is_kept(alice: Actor) -> None:
    # The alice fixture already granted the service consent.
    again = alice.consent("service", "2026-10-11")
    assert again.status_code == 200
    assert len(alice.get("/v1/consents").json()["items"]) == 1

    newer = alice.consent("service", "2026-11-01").json()
    assert newer["version"] == "2026-11-01" and newer["active"] is True
    items = alice.get("/v1/consents").json()["items"]
    assert [(c["version"], c["active"]) for c in items] == [("2026-11-01", True), ("2026-10-11", False)]

    revoked = alice.delete("/v1/consents/service")
    assert revoked.status_code == 200 and revoked.json()["active"] is False
    assert alice.delete("/v1/consents/service").status_code == 404
    assert all(not c["active"] for c in alice.get("/v1/consents").json()["items"])


def test_consent_types_and_versions_are_validated(alice: Actor) -> None:
    assert alice.consent("marketing").status_code == 422
    assert alice.put("/v1/consents/illustration", json={"version": "has spaces"}).status_code == 422
    assert alice.put("/v1/consents/illustration", json={}).status_code == 422
    assert alice.consent("illustration").json()["consent_type"] == "illustration"


def test_consents_are_separate(alice: Actor, bob: Actor) -> None:
    alice.consent("photo_storage")
    assert {c["consent_type"] for c in alice.get("/v1/consents").json()["items"]} == {"service", "photo_storage"}
    assert {c["consent_type"] for c in bob.get("/v1/consents").json()["items"]} == {"service"}
    assert bob.delete("/v1/consents/photo_storage").status_code == 404
