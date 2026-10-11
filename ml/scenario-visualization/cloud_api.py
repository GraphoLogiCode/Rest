"""Private service: only the authenticated Rest backend may call this API."""
from contextlib import asynccontextmanager
import hmac
import json
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Query
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from job_worker import JobError, JobQueue, WorkerSettings, run_model

MAX_BODY = 11 * 1024 * 1024


async def bounded_form(request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY:
            raise JobError(413, "Upload is too large.")
    async def receive():
        return {"type": "http.request", "body": bytes(body), "more_body": False}
    clone = Request(request.scope, receive)
    # Keep the context manager so the caller reliably closes upload spools.
    return clone.form(max_files=1, max_fields=3, max_part_size=16 * 1024)


def create_app(settings=None, *, runner=run_model):
    settings = settings or WorkerSettings.from_env()
    queue = JobQueue(settings, runner)

    @asynccontextmanager
    async def lifespan(app):
        queue.start()
        try:
            yield
        finally:
            await run_in_threadpool(queue.close)

    app = FastAPI(title="Rest private GPU worker", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.queue = queue

    @app.exception_handler(JobError)
    async def job_error(request, exc):
        return JSONResponse({"error": exc.message}, status_code=exc.status)

    @app.middleware("http")
    async def private_headers(request, call_next):
        response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        return response

    def owner(request: Request):
        if not hmac.compare_digest(request.headers.get("authorization", "").encode(), ("Bearer " + settings.token).encode()):
            raise JobError(401, "Service authentication required.")
        try:
            return str(UUID(request.headers.get("x-rest-user-id", "")))
        except ValueError:
            raise JobError(422, "A valid owner is required.") from None

    @app.get("/healthz")
    def health():
        if queue.thread is None or not queue.thread.is_alive():
            raise JobError(503, "Worker unavailable.")
        return {"status": "ok"}

    @app.post("/jobs", status_code=202)
    async def create(request: Request, user=Depends(owner)):
        try:
            key = str(UUID(request.headers.get("idempotency-key", "")))
            async with await bounded_form(request) as form:
                if sorted(form.keys()) != ["consent", "options", "reference"] or len(form.multi_items()) != 3:
                    raise ValueError()
                if form["consent"] != "true" or not isinstance(form["reference"], UploadFile):
                    raise ValueError()
                options = json.loads(form["options"])
                raw = await form["reference"].read()
            return await run_in_threadpool(queue.create, user, key, raw, options)
        except (ValueError, TypeError):
            raise JobError(422, "Provide a photo, consent, supported options and an Idempotency-Key UUID.") from None

    @app.get("/usage")
    def usage(after: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), user=Depends(owner)):
        return queue.usage(user, after, limit)

    @app.delete("/usage")
    def purge_usage(user=Depends(owner)):
        return {"deleted": queue.purge_usage(user)}

    @app.get("/jobs")
    def list_jobs(user=Depends(owner)):
        return {"items": queue.list(user)}

    @app.get("/jobs/{key}")
    def status(key: UUID, user=Depends(owner)):
        return queue.status(user, str(key))

    @app.get("/jobs/{key}/image")
    def image(key: UUID, user=Depends(owner)):
        return Response(queue.image(user, str(key)), media_type="image/png")

    @app.delete("/jobs/{key}", status_code=204)
    def delete(key: UUID, user=Depends(owner)):
        queue.delete(user, str(key))
        return Response(status_code=204)

    @app.delete("/jobs")
    def purge(user=Depends(owner)):
        return {"deleted": queue.purge(user)}

    return app
