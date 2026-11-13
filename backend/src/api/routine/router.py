from src.visualization.client import owner_lock
from fastapi import APIRouter
from src.auth import CurrentUser
from src.storage import StoreDep
from src.errors import ApiError
from src.privacy.consent import require_consent
from src.timestamps import today_in
from .schemas import RoutineDocument

router = APIRouter(prefix='/v1/routine', tags=['routine'])

@router.get('', response_model=RoutineDocument)
def get(user: CurrentUser, store: StoreDep):
    return store.get_routine(user.id)

@router.put('', response_model=RoutineDocument, dependencies=[require_consent('service')])
async def save(body: RoutineDocument, user: CurrentUser, store: StoreDep):
    async with owner_lock(user.id, store):
        if not store.active_consent(user.id, "service"):
            raise ApiError(403, "consent_required", "Account saving must be enabled.")
        if len({item.id for item in body.items}) != len(body.items):
            raise ApiError(422, 'duplicate_step', 'Routine step IDs must be unique.')
        today = today_in(store.get_or_create_profile(user.id).timezone)
        if any(item.completedOn and item.completedOn > today for item in body.items):
            raise ApiError(422, 'date_in_future', 'A completion cannot be in the future.')
        result = store.save_routine(user.id, body.version, [item.model_dump(mode='json', exclude_none=True) for item in body.items])
        if result is None:
            raise ApiError(409, 'routine_conflict', 'Your routine changed on another device. Reload before editing.')
        return result
