import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.api.checkins.router import router as checkins_router
from src.api.routine.router import router as routine_router
from src.api.progress.router import router as progress_router
from src.api.profile.router import router as profile_router
from src.auth import TokenVerifier
from src.catalog.service import Catalog
from src.catalog.router import router as catalog_router
from src.recommendations.router import router as recommendations_router
from src.config import Settings
from src.context.router import router as context_router
from src.errors import install_error_handlers
from src.privacy.router import router as privacy_router
from src.storage import MemoryStore, Store

from src.visualization.client import ModelClient
from src.visualization.router import router as illustration_router

logger = logging.getLogger("rest.api")


def build_store(settings: Settings) -> Store:
    if settings.database_url:
        from src.storage.postgres import PostgresStore

        return PostgresStore(settings.database_url)
    logger.warning("DATABASE_URL is not set: using in-memory storage. Data is lost on restart.")
    return MemoryStore()


def create_app(
    settings: Settings | None = None,
    *,
    store: Store | None = None,
    token_verifier: TokenVerifier | None = None,
    model_client: ModelClient | None = None,
    catalog: Catalog | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        app.state.store.close()
        if app.state.model_client:
            await app.state.model_client.close()

    app = FastAPI(title="Rest API", version="0.1.0", lifespan=lifespan)
    app.state.catalog = catalog or Catalog()
    app.state.store = store or build_store(settings)
    app.state.token_verifier = token_verifier or TokenVerifier.from_settings(settings)
    app.state.model_client = model_client or (ModelClient(settings.model_service_url, settings.model_service_token)
                                              if settings.model_service_url else None)
    install_error_handlers(app)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    @app.middleware("http")
    async def never_cache(request: Request, call_next) -> Response:
        # Responses carry personal data; keep them out of shared and browser caches.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    for router in (catalog_router, recommendations_router, progress_router, routine_router, profile_router, checkins_router, context_router, privacy_router, illustration_router):
        app.include_router(router)
    return app
