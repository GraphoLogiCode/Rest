import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_jwt_secret: str | None = None
    jwt_audience: str = "authenticated"
    database_url: str | None = None
    cors_origins: tuple[str, ...] = ()

    model_service_url: str | None = None
    model_service_token: str | None = None

    def __post_init__(self):
        if bool(self.model_service_url) != bool(self.model_service_token):
            raise ValueError("Set MODEL_SERVICE_URL and MODEL_SERVICE_TOKEN together")
        if self.model_service_token and len(self.model_service_token) < 32:
            raise ValueError("MODEL_SERVICE_TOKEN must have at least 32 characters")

    @property
    def issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        supabase_url = env.get("SUPABASE_URL", "").strip()
        if not supabase_url:
            # Without the project URL there is no issuer to trust, so refuse to start.
            raise RuntimeError("SUPABASE_URL is required")
        origins = tuple(o.strip() for o in env.get("CORS_ORIGINS", "").split(",") if o.strip())
        return cls(
            supabase_url=supabase_url,
            supabase_jwt_secret=env.get("SUPABASE_JWT_SECRET", "").strip() or None,
            jwt_audience=env.get("SUPABASE_JWT_AUDIENCE", "").strip() or "authenticated",
            database_url=env.get("DATABASE_URL", "").strip() or None,
            cors_origins=origins,
            model_service_url=env.get("MODEL_SERVICE_URL", "").strip() or None,
            model_service_token=env.get("MODEL_SERVICE_TOKEN", "").strip() or None,
        )
