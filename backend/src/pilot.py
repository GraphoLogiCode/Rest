"""One AWS-managed HTTPS origin for the app and authenticated API."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.config import Settings
from src.main import create_app as create_api


def create_app():
    settings = Settings.from_env()
    if not settings.database_url:
        raise RuntimeError('Managed deployment requires DATABASE_URL; memory storage is disabled.')
    if settings.model_service_url:
        raise RuntimeError('Illustration workers are disabled in the real-progress pilot.')
    api = create_api(settings)

    @asynccontextmanager
    async def lifespan(app):
        async with api.router.lifespan_context(api):
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount('/rest-api', api)
    app.mount('/', StaticFiles(directory=os.environ.get('REST_FRONTEND_DIR', '/app/frontend'), html=True))
    return app
