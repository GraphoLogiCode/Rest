"""Server-to-server calls. Browser identity is always taken from a verified JWT."""
import asyncio
from contextlib import asynccontextmanager
from weakref import WeakValueDictionary

import httpx
from fastapi import Request
from src.errors import ApiError

_locks = WeakValueDictionary()


@asynccontextmanager
async def owner_lock(owner, store=None):
    # Local lock bounds same-process contention; Postgres adds a shared lock
    # across containers for progress, consent revocation and account deletion.
    key = str(owner)
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if store is not None and hasattr(store, "progress_owner_lock"):
            async with store.progress_owner_lock(owner):
                yield
        else:
            yield


class ModelClient:
    def __init__(self, url, token, *, transport=None):
        self.http = httpx.AsyncClient(base_url=url.rstrip("/") + "/", transport=transport,
                                      timeout=httpx.Timeout(25, connect=5), follow_redirects=False)
        self.token = token

    async def call(self, method, path, owner, **kwargs):
        headers = {"Authorization": "Bearer " + self.token, "X-Rest-User-ID": str(owner),
                   **kwargs.pop("headers", {})}
        try:
            response = await self.http.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(503, "model_unavailable", "The illustration service is unavailable. Try again shortly.") from exc
        if response.is_error or response.is_redirect:
            code = response.status_code if response.status_code in (404, 409, 410, 413, 422, 429) else 503
            messages = {404: "Job not found or expired.", 409: "The job is not ready, or the request key was reused with different input.",
                        410: "This illustration has expired.", 413: "Choose an image under 10 MB.",
                        422: "Check the photo and selected regions.", 429: "The illustration queue is full. Please try again later."}
            raise ApiError(code, "illustration_error", messages.get(code, "The illustration service is unavailable. Please retry."))
        return response

    async def purge(self, owner):
        return (await self.call("DELETE", "jobs", owner)).json()["deleted"]

    async def close(self):
        await self.http.aclose()


def model_client(request: Request):
    client = request.app.state.model_client
    if client is None:
        raise ApiError(503, "model_not_configured", "Cloud illustrations are not configured yet.")
    return client
