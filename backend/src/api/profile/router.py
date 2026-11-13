from src.errors import ApiError
from src.visualization.client import owner_lock
from fastapi import APIRouter

from src.api.profile.schemas import ProfileOut, ProfileUpdate
from src.auth import CurrentUser
from src.storage import StoreDep

router = APIRouter(prefix="/v1", tags=["profile"])


@router.get("/me", response_model=ProfileOut)
def read_me(user: CurrentUser, store: StoreDep) -> ProfileOut:
    return ProfileOut.from_profile(store.get_or_create_profile(user.id))


@router.patch("/me", response_model=ProfileOut)
async def update_me(body: ProfileUpdate, user: CurrentUser, store: StoreDep) -> ProfileOut:
    async with owner_lock(user.id, store):
        if not store.active_consent(user.id, "service"):
            raise ApiError(403, "consent_required", "Account saving must be enabled.")
        changes = body.model_dump(exclude_unset=True)
        if "budget" in changes:
            budget = changes.pop("budget")
            changes["budget_amount"] = budget["amount"] if budget else None
            changes["budget_currency"] = budget["currency"] if budget else None
        return ProfileOut.from_profile(store.update_profile(user.id, changes))
