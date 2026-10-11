from datetime import datetime, timezone

from fastapi import APIRouter, Request

from src.api.checkins.schemas import CheckInOut
from src.api.profile.schemas import ProfileOut
from src.auth import CurrentUser
from src.context.schemas import InsightOut
from src.errors import not_found
from src.privacy.schemas import AccountDeleted, ConsentGrant, ConsentList, ConsentOut, ConsentType, ExportOut
from src.storage import StoreDep

from src.visualization.client import owner_lock

router = APIRouter(prefix="/v1", tags=["privacy"])


@router.get("/consents", response_model=ConsentList)
def list_consents(user: CurrentUser, store: StoreDep) -> ConsentList:
    return ConsentList(items=[ConsentOut.model_validate(c) for c in store.list_consents(user.id)])


@router.put("/consents/{consent_type}", response_model=ConsentOut)
async def grant_consent(consent_type: ConsentType, body: ConsentGrant, user: CurrentUser, store: StoreDep) -> ConsentOut:
    async with owner_lock(user.id, store):
        return ConsentOut.model_validate(store.grant_consent(user.id, consent_type, body.version))


@router.delete("/consents/{consent_type}", response_model=ConsentOut)
async def revoke_consent(consent_type: ConsentType, request: Request, user: CurrentUser, store: StoreDep) -> ConsentOut:
    async with owner_lock(user.id, store):
        if store.active_consent(user.id, consent_type) is None:
            raise not_found("Active consent")
        if consent_type == "illustration" and request.app.state.model_client:
            await request.app.state.model_client.purge(user.id)
        if consent_type == "photo_storage":
            store.purge_photos(user.id)
        revoked = store.revoke_consent(user.id, consent_type)
        return ConsentOut.model_validate(revoked)


@router.post("/export", response_model=ExportOut)
async def export_my_data(request: Request, user: CurrentUser, store: StoreDep) -> ExportOut:
    async with owner_lock(user.id, store):
        """Includes temporary illustration job metadata; image bytes use authenticated download."""
        jobs = []
        usage = []
        if request.app.state.model_client:
            jobs = (await request.app.state.model_client.call("GET", "jobs", user.id)).json()["items"]
            cursor = 0
            while True:
                page = (await request.app.state.model_client.call("GET", "usage", user.id,
                        params={"after": cursor, "limit": 500})).json()
                usage.extend(page["items"])
                cursor = page["nextCursor"]
                if cursor is None:
                    break
        return ExportOut(
            exported_at=datetime.now(timezone.utc),
            profile=ProfileOut.from_profile(store.get_or_create_profile(user.id)),
            consents=[ConsentOut.model_validate(c) for c in store.list_consents(user.id)],
            checkins=[CheckInOut.model_validate(c) for c in store.list_checkins(user.id)],
            insights=[InsightOut.model_validate(i) for i in store.list_insights(user.id)],
            illustration_jobs=jobs,
            illustration_usage=usage,
            routine=store.get_routine(user.id),
            recommendations=store.list_progress(user.id, 'recommendation'),
            recommendation_feedback=store.list_progress(user.id, 'feedback'),
            usage_reports=store.list_progress(user.id, 'usage'),
            photos=store.list_progress(user.id, 'photo'),
        )


@router.delete("/account", response_model=AccountDeleted)
async def delete_my_data(request: Request, user: CurrentUser, store: StoreDep) -> AccountDeleted:
    async with owner_lock(user.id, store):
        count = None
        if request.app.state.model_client:
            count = await request.app.state.model_client.purge(user.id)
            await request.app.state.model_client.call("DELETE", "usage", user.id)
        deleted = store.delete_user_data(user.id)
        if count is not None:
            deleted["illustration_jobs"] = count
        return AccountDeleted(deleted=deleted, auth_identity_deleted=False)
