from typing import Annotated
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, StringConstraints
from src.auth import CurrentUser
from src.storage import StoreDep
from src.privacy.consent import require_consent
from src.catalog.service import Category
from .engine import recommend
from uuid import uuid4
from src.visualization.client import owner_lock
from src.errors import ApiError
router=APIRouter(prefix='/v1/recommendations', tags=['recommendations'])
class Query(BaseModel):
    model_config=ConfigDict(extra='forbid')
    category: Category
    goal: Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=100)]|None=None
    texture: Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=40)]|None=None

@router.post('', dependencies=[require_consent('service')])
async def suggestions(body:Query, request:Request,user:CurrentUser,store:StoreDep):
    async with owner_lock(user.id, store):
        if not store.active_consent(user.id, 'service'):
            raise ApiError(403, 'consent_required', 'Account saving must be enabled.')
        profile = store.get_or_create_profile(user.id)
        result = recommend(request.app.state.catalog,profile,body.category,body.goal,body.texture)
        consent = store.active_consent(user.id, 'model_training')
        identifier = uuid4()
        store.create_progress(user.id, identifier, 'recommendation', {'query': body.model_dump(), 'result': result, 'profile_snapshot': {'skin_type': profile.skin_type, 'ingredient_exclusions': profile.ingredient_exclusions, 'budget_amount': profile.budget_amount, 'budget_currency': profile.budget_currency}, 'training_consent_at_collection': str(consent.id) if consent else None}, str(identifier))
        return {**result, 'recommendation_id': str(identifier)}
