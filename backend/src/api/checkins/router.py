from src.visualization.client import owner_lock
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.api.checkins.schemas import CheckInCreate, CheckInList, CheckInOut, CheckInUpdate
from src.auth import CurrentUser
from src.errors import ApiError, not_found
from src.privacy.consent import require_consent
from src.storage import CheckInExists, StoreDep
from src.storage.models import CHECKIN_SCALE_VERSION, CHECKIN_VALUES
from src.timestamps import today_in

router = APIRouter(prefix="/v1/checkins", tags=["check-ins"])

# Check-ins hold sleep, mood, and stress, so nothing is stored without consent.
# Reading, exporting, and deleting stay available after consent is revoked.
ServiceConsent = require_consent("service")


@router.post("", status_code=201, response_model=CheckInOut, dependencies=[ServiceConsent])
async def create_checkin(body: CheckInCreate, user: CurrentUser, store: StoreDep) -> CheckInOut:
    async with owner_lock(user.id, store):
        if not store.active_consent(user.id, "service"):
            raise ApiError(403, "consent_required", "Account saving must be enabled.")
        profile = store.get_or_create_profile(user.id)
        today = today_in(profile.timezone)
        if body.local_date > today:
            raise ApiError(422, "date_in_future", f"local_date is after today ({today}) in {profile.timezone}.")
        values = body.model_dump(exclude={"local_date"})
        try:
            checkin = store.create_checkin(user.id, body.local_date, profile.timezone, CHECKIN_SCALE_VERSION, values)
        except CheckInExists as exc:
            raise ApiError(
                409, "checkin_exists", "There is already a check-in for this date. Edit it instead.",
                details={"checkin_id": str(exc.checkin_id)},
            ) from exc
        return CheckInOut.model_validate(checkin)


@router.patch("/{checkin_id}", response_model=CheckInOut, dependencies=[ServiceConsent])
async def update_checkin(checkin_id: UUID, body: CheckInUpdate, user: CurrentUser, store: StoreDep) -> CheckInOut:
    async with owner_lock(user.id, store):
        if not store.active_consent(user.id, "service"):
            raise ApiError(403, "consent_required", "Account saving must be enabled.")
        current = store.get_checkin(user.id, checkin_id)
        if current is None:
            raise not_found("Check-in")
        changes = body.model_dump(exclude_unset=True)
        if all(changes.get(name, getattr(current, name)) is None for name in CHECKIN_VALUES):
            raise ApiError(422, "empty_checkin", "A check-in needs at least one value.")
        updated = store.update_checkin(user.id, checkin_id, changes)
        if updated is None:
            raise not_found("Check-in")
        return CheckInOut.model_validate(updated)


@router.get("", response_model=CheckInList)
def list_checkins(
    user: CurrentUser,
    store: StoreDep,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> CheckInList:
    if start is not None and end is not None and start > end:
        raise ApiError(422, "invalid_range", "'from' must not be after 'to'.")
    items = [CheckInOut.model_validate(c) for c in store.list_checkins(user.id, start, end)]
    return CheckInList(items=items)
