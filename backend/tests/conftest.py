"""Shared fixtures.

The API tests run against the in-memory store, and again against Postgres when
REST_TEST_DATABASE_URL points at a local or throwaway database. Never point it
at a database that holds real data: the tests create and delete users.
"""

import os
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from src.auth import TokenVerifier
from src.config import Settings
from src.main import create_app
from src.storage import MemoryStore, Store

SUPABASE_URL = "https://project.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
SECRET = "test-only-secret-long-enough-for-hs256-signing"
MIGRATIONS = Path(__file__).resolve().parents[2] / "data" / "migrations"

# Stands in for what a Supabase project already provides.
SUPABASE_SHIM = """
create schema auth;
create table auth.users (id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;
create role anon nologin;
create role authenticated nologin;
grant usage on schema public, auth to anon, authenticated;
"""


def make_token(user_id: uuid.UUID | None = None, *, secret: Any = SECRET, algorithm: str = "HS256", **claims: Any) -> str:
    """A token shaped like a Supabase access token. Pass a claim as None to leave it out."""
    payload: dict[str, Any] = {
        "sub": str(user_id or uuid.uuid4()),
        "aud": "authenticated",
        "iss": ISSUER,
        "role": "authenticated",
        "exp": int(time.time()) + 600,
        **claims,
    }
    payload = {name: value for name, value in payload.items() if value is not None}
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture(scope="session")
def pg_url() -> str:
    url = os.environ.get("REST_TEST_DATABASE_URL")
    if not url:
        pytest.skip("REST_TEST_DATABASE_URL is not set")
    with psycopg.connect(url, autocommit=True) as conn:
        if conn.execute("select to_regnamespace('auth') is null").fetchone()[0]:
            conn.execute(SUPABASE_SHIM)
        if conn.execute("select to_regclass('public.profiles') is null").fetchone()[0]:
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                conn.execute(migration.read_text())
        elif conn.execute("select to_regclass('public.routine_state') is null").fetchone()[0]:
            conn.execute((MIGRATIONS / '0002_routine_state.sql').read_text())
        if conn.execute("select to_regclass('public.progress_records') is null").fetchone()[0]:
            conn.execute((MIGRATIONS / '0003_progress_records.sql').read_text())
    return url


@pytest.fixture(params=["memory", "postgres"])
def backend(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def store(backend: str, request: pytest.FixtureRequest) -> Iterator[Store]:
    if backend == "memory":
        yield MemoryStore()
        return
    from src.storage.postgres import PostgresStore

    store = PostgresStore(request.getfixturevalue("pg_url"), max_connections=2)
    yield store
    store.close()


@pytest.fixture
def new_user(backend: str, request: pytest.FixtureRequest) -> Iterator[Callable[[], uuid.UUID]]:
    """Creates a user id, registering it as a sign-in identity when the database needs one."""
    created: list[uuid.UUID] = []
    url = request.getfixturevalue("pg_url") if backend == "postgres" else None

    def create() -> uuid.UUID:
        user_id = uuid.uuid4()
        if url:
            with psycopg.connect(url, autocommit=True) as conn:
                conn.execute("insert into auth.users (id) values (%s)", [user_id])
        created.append(user_id)
        return user_id

    yield create
    if url and created:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("delete from auth.users where id = any(%s)", [created])


@pytest.fixture
def settings() -> Settings:
    return Settings(supabase_url=SUPABASE_URL, supabase_jwt_secret=SECRET)


@pytest.fixture
def client(settings: Settings, store: Store) -> Iterator[TestClient]:
    verifier = TokenVerifier(issuer=settings.issuer, jwt_secret=SECRET)
    app = create_app(settings, store=store, token_verifier=verifier)
    # The store fixture owns the store's lifetime, so the app's shutdown hook is not run.
    yield TestClient(app)


class Actor:
    """A signed-in user making requests."""

    def __init__(self, client: TestClient, user_id: uuid.UUID):
        self.client = client
        self.id = user_id
        self.headers = {"Authorization": f"Bearer {make_token(user_id)}"}

    def request(self, method: str, path: str, **kwargs: Any):
        return self.client.request(method, path, headers=self.headers, **kwargs)

    def get(self, path: str, **kwargs: Any):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any):
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any):
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any):
        return self.request("DELETE", path, **kwargs)

    def consent(self, consent_type: str = "service", version: str = "2026-10-11"):
        return self.put(f"/v1/consents/{consent_type}", json={"version": version})


@pytest.fixture
def alice(client: TestClient, new_user: Callable[[], uuid.UUID]) -> Actor:
    """A user who has given the service consent."""
    actor = Actor(client, new_user())
    assert actor.consent().status_code == 200
    return actor


@pytest.fixture
def bob(client: TestClient, new_user: Callable[[], uuid.UUID]) -> Actor:
    """A second user who has given the service consent."""
    actor = Actor(client, new_user())
    assert actor.consent().status_code == 200
    return actor
