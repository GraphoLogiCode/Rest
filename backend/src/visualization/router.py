import json
from uuid import UUID

from fastapi import APIRouter, Request, Response, Query
from starlette.datastructures import UploadFile
from src.auth import CurrentUser
from src.errors import ApiError
from src.storage import StoreDep
from src.visualization.client import model_client, owner_lock

router = APIRouter(prefix="/v1", tags=["illustrations"])


def public_job(value):
    # Build the image path here; never relay an arbitrary URL to the browser.
    try:
        key = str(UUID(value["id"]))
        if value["status"] not in {"queued", "running", "completed", "failed"}:
            raise ValueError()
        result = {k: value[k] for k in ("status", "mode", "createdAt", "expiresAt", "disclaimer", "progress",
                                      "progressStage", "completedSteps", "totalSteps", "error") if k in value}
        result["id"] = key
        if value["status"] == "completed":
            result["imageUrl"] = f"/v1/jobs/{key}/image"
        return result
    except (ValueError, KeyError, TypeError):
        raise ApiError(502, "model_response_invalid", "The illustration service returned an invalid response.") from None


async def upload_form(request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 11 * 1024 * 1024:
            raise ApiError(413, "image_too_large", "Choose an image under 10 MB.")
    async def receive():
        return {"type": "http.request", "body": bytes(body), "more_body": False}
    # Return the context manager, not an already-awaited FormData. The caller closes uploads.
    return Request(request.scope, receive).form(max_files=1, max_fields=3, max_part_size=16 * 1024)


@router.post("/illustrations", status_code=202)
async def create(request: Request, user: CurrentUser, store: StoreDep):
    client = model_client(request)
    async with owner_lock(user.id, store):
        if store.active_consent(user.id, "illustration") is None:
            raise ApiError(403, "consent_required", "Illustration consent is required.")
        try:
            key = str(UUID(request.headers.get("idempotency-key", "")))
            async with await upload_form(request) as form:
                if sorted(form.keys()) != ["consent", "options", "reference"] or len(form.multi_items()) != 3:
                    raise ValueError()
                if form["consent"] != "true" or not isinstance(form["reference"], UploadFile):
                    raise ValueError()
                options = json.loads(form["options"])
                raw = await form["reference"].read()
                if len(raw) > 10 * 1024 * 1024:
                    raise ApiError(413, "image_too_large", "Choose an image under 10 MB.")
        except (ValueError, TypeError):
            raise ApiError(422, "invalid_illustration", "Provide a photo, consent, options and an Idempotency-Key UUID.") from None
        response = await client.call("POST", "jobs", user.id, headers={"Idempotency-Key": key},
                                     data={"consent": "true", "options": json.dumps(options)},
                                     files={"reference": ("reference", raw, "application/octet-stream")})
        return public_job(response.json())


@router.get("/billing/usage")
async def usage(request: Request, user: CurrentUser, after: int = Query(0, ge=0),
                limit: int = Query(100, ge=1, le=500)):
    # Owner always comes from the verified JWT, never a browser-supplied customer ID.
    response = await model_client(request).call("GET", "usage", user.id, params={"after": after, "limit": limit})
    return {"billingMode": "tracking_only", "paymentsEnabled": False, **response.json()}


@router.get("/jobs")
async def jobs(request: Request, user: CurrentUser):
    response = await model_client(request).call("GET", "jobs", user.id)
    return {"items": [public_job(v) for v in response.json()["items"]]}


@router.get("/jobs/{key}")
async def job(key: UUID, request: Request, user: CurrentUser):
    return public_job((await model_client(request).call("GET", f"jobs/{key}", user.id)).json())


@router.get("/jobs/{key}/image")
async def image(key: UUID, request: Request, user: CurrentUser):
    result = await model_client(request).call("GET", f"jobs/{key}/image", user.id)
    return Response(result.content, media_type="image/png", headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/jobs/{key}", status_code=204)
async def delete(key: UUID, request: Request, user: CurrentUser):
    await model_client(request).call("DELETE", f"jobs/{key}", user.id)
    return Response(status_code=204)
