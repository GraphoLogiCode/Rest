import threading
import uuid
from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from src.storage.base import CheckInExists, check_checkin_values, check_profile_changes
from src.storage.models import CheckIn, Consent, Insight, Profile


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStore:
    """Keeps everything in process memory. For tests and local runs only."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: dict[UUID, Profile] = {}
        self._consents: list[Consent] = []
        self._checkins: dict[UUID, CheckIn] = {}
        self._routines: dict[UUID, dict] = {}
        self._insights: dict[UUID, Insight] = {}
        self._progress: dict[UUID, dict] = {}

    def _profile(self, user_id: UUID) -> Profile:
        if user_id not in self._profiles:
            now = _now()
            self._profiles[user_id] = Profile(
                user_id=user_id, timezone="UTC", goals=[], skin_type=None, concerns=None,
                ingredient_exclusions=None, budget_amount=None, budget_currency=None,
                created_at=now, updated_at=now,
            )
        return self._profiles[user_id]

    def get_or_create_profile(self, user_id: UUID) -> Profile:
        with self._lock:
            return deepcopy(self._profile(user_id))

    def update_profile(self, user_id: UUID, changes: dict[str, Any]) -> Profile:
        check_profile_changes(changes)
        with self._lock:
            profile = self._profile(user_id)
            if changes:
                for name, value in changes.items():
                    setattr(profile, name, deepcopy(value))
                profile.updated_at = _now()
            return deepcopy(profile)

    def list_consents(self, user_id: UUID) -> list[Consent]:
        with self._lock:
            owned = [c for c in self._consents if c.user_id == user_id]
            return deepcopy(sorted(owned, key=lambda c: c.granted_at, reverse=True))

    def _active(self, user_id: UUID, consent_type: str) -> Consent | None:
        for consent in self._consents:
            if consent.user_id == user_id and consent.consent_type == consent_type and consent.revoked_at is None:
                return consent
        return None

    def active_consent(self, user_id: UUID, consent_type: str) -> Consent | None:
        with self._lock:
            return deepcopy(self._active(user_id, consent_type))

    def grant_consent(self, user_id: UUID, consent_type: str, version: str) -> Consent:
        with self._lock:
            now = _now()
            active = self._active(user_id, consent_type)
            if active is not None:
                if active.version == version:
                    return deepcopy(active)
                active.revoked_at = now
            consent = Consent(
                id=uuid.uuid4(), user_id=user_id, consent_type=consent_type,
                version=version, granted_at=now, revoked_at=None,
            )
            self._consents.append(consent)
            return deepcopy(consent)

    def revoke_consent(self, user_id: UUID, consent_type: str) -> Consent | None:
        with self._lock:
            active = self._active(user_id, consent_type)
            if active is None:
                return None
            active.revoked_at = _now()
            return deepcopy(active)

    def create_checkin(
        self, user_id: UUID, local_date: date, timezone: str, scale_version: str, values: dict[str, Any]
    ) -> CheckIn:
        check_checkin_values(values)
        with self._lock:
            for existing in self._checkins.values():
                if existing.user_id == user_id and existing.local_date == local_date:
                    raise CheckInExists(existing.id)
            now = _now()
            checkin = CheckIn(
                id=uuid.uuid4(), user_id=user_id, local_date=local_date, timezone=timezone,
                scale_version=scale_version, sleep_hours=values.get("sleep_hours"),
                sleep_quality=values.get("sleep_quality"), mood=values.get("mood"),
                stress=values.get("stress"), connection=values.get("connection"),
                note=values.get("note"), created_at=now, updated_at=now,
            )
            self._checkins[checkin.id] = checkin
            return deepcopy(checkin)

    def _owned_checkin(self, user_id: UUID, checkin_id: UUID) -> CheckIn | None:
        checkin = self._checkins.get(checkin_id)
        return checkin if checkin is not None and checkin.user_id == user_id else None

    def get_checkin(self, user_id: UUID, checkin_id: UUID) -> CheckIn | None:
        with self._lock:
            return deepcopy(self._owned_checkin(user_id, checkin_id))

    def update_checkin(self, user_id: UUID, checkin_id: UUID, changes: dict[str, Any]) -> CheckIn | None:
        check_checkin_values(changes)
        with self._lock:
            checkin = self._owned_checkin(user_id, checkin_id)
            if checkin is None:
                return None
            if changes:
                for name, value in changes.items():
                    setattr(checkin, name, value)
                checkin.updated_at = _now()
            return deepcopy(checkin)

    def list_checkins(self, user_id: UUID, start: date | None = None, end: date | None = None) -> list[CheckIn]:
        with self._lock:
            owned = [
                c for c in self._checkins.values()
                if c.user_id == user_id
                and (start is None or c.local_date >= start)
                and (end is None or c.local_date <= end)
            ]
            return deepcopy(sorted(owned, key=lambda c: c.local_date, reverse=True))

    def save_insight(
        self, user_id: UUID, period_start: date, period_end: date, input_version: str, rule_version: str, text: str
    ) -> Insight:
        with self._lock:
            key = (user_id, period_start, period_end, input_version, rule_version)
            for existing in self._insights.values():
                if (existing.user_id, existing.period_start, existing.period_end,
                        existing.input_version, existing.rule_version) == key:
                    return deepcopy(existing)
            insight = Insight(
                id=uuid.uuid4(), user_id=user_id, period_start=period_start, period_end=period_end,
                input_version=input_version, rule_version=rule_version, text=text,
                feedback=None, feedback_at=None, created_at=_now(),
            )
            self._insights[insight.id] = insight
            return deepcopy(insight)

    def list_insights(self, user_id: UUID) -> list[Insight]:
        with self._lock:
            owned = [i for i in self._insights.values() if i.user_id == user_id]
            return deepcopy(sorted(owned, key=lambda i: i.created_at, reverse=True))

    def set_insight_feedback(self, user_id: UUID, insight_id: UUID, feedback: str) -> Insight | None:
        with self._lock:
            insight = self._insights.get(insight_id)
            if insight is None or insight.user_id != user_id:
                return None
            insight.feedback = feedback
            insight.feedback_at = _now()
            return deepcopy(insight)

    def get_routine(self, user_id: UUID) -> dict:
        with self._lock:
            return deepcopy(self._routines.get(user_id, {"items": [], "version": 0}))

    def save_routine(self, user_id: UUID, version: int, items: list[dict]) -> dict | None:
        with self._lock:
            current = self._routines.get(user_id, {"items": [], "version": 0})
            if current["version"] != version:
                return None
            value = {"items": deepcopy(items), "version": version + 1}
            self._routines[user_id] = value
            return deepcopy(value)

    def create_progress(self, user_id, entry_id, kind, payload, fingerprint, image=None):
        from src.errors import ApiError
        with self._lock:
            old = self._progress.get(entry_id)
            if old:
                if old['user_id'] != user_id or old['fingerprint'] != fingerprint or old['kind'] != kind:
                    raise ApiError(409, 'entry_conflict', 'Use a new entry ID for a different report.')
                return self._public_progress(old)
            limit = 12 if kind == 'photo' else 1000
            if sum(r['user_id']==user_id and r['kind']==kind for r in self._progress.values()) >= limit:
                raise ApiError(409, 'storage_limit', 'Your pilot storage limit is reached. Export or delete older entries first.')
            row = dict(id=str(entry_id), user_id=user_id, kind=kind, payload=deepcopy(payload),
                       fingerprint=fingerprint, photo_bytes=image, created_at=_now().isoformat())
            self._progress[entry_id] = row
            return self._public_progress(row)

    @staticmethod
    def _public_progress(row):
        return deepcopy({k:row[k] for k in ('id','kind','payload','created_at')})

    def list_progress(self, user_id, kind):
        with self._lock:
            return [self._public_progress(r) for r in sorted(self._progress.values(), key=lambda r:r['created_at'], reverse=True)
                    if r['user_id']==user_id and r['kind']==kind]

    def progress_image(self, user_id, entry_id):
        with self._lock:
            row=self._progress.get(entry_id)
            return row['photo_bytes'] if row and row['user_id']==user_id and row['kind']=='photo' else None

    def delete_progress(self, user_id, entry_id):
        with self._lock:
            row=self._progress.get(entry_id)
            if not row or row['user_id']!=user_id:return False
            del self._progress[entry_id]
            return True

    def purge_photos(self, user_id):
        with self._lock:
            ids=[k for k,r in self._progress.items() if r['user_id']==user_id and r['kind']=='photo']
            for key in ids:del self._progress[key]
            return len(ids)

    def delete_user_data(self, user_id: UUID) -> dict[str, int]:
        with self._lock:
            counts = {
                "progress_records": sum(r['user_id']==user_id for r in self._progress.values()),
                "insights": sum(1 for i in self._insights.values() if i.user_id == user_id),
                "checkins": sum(1 for c in self._checkins.values() if c.user_id == user_id),
                "consents": sum(1 for c in self._consents if c.user_id == user_id),
                "profiles": 1 if user_id in self._profiles else 0,
            }
            self._insights = {k: v for k, v in self._insights.items() if v.user_id != user_id}
            self._checkins = {k: v for k, v in self._checkins.items() if v.user_id != user_id}
            self._consents = [c for c in self._consents if c.user_id != user_id]
            routine = self._routines.pop(user_id, None)
            counts["routine_state"] = int(routine is not None)
            self._profiles.pop(user_id, None)
            self._progress = {k:r for k,r in self._progress.items() if r['user_id']!=user_id}
            return counts

    def close(self) -> None:
        pass
