"""The database's own protections, checked with plain SQL.

These run only against Postgres. They prove that row-level security and column
grants hold even for a client that skips the API and talks to the tables directly.
"""

import json
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import psycopg
import pytest
from psycopg import errors

from src.storage.postgres import PostgresStore

TABLES = ("profiles", "consents", "checkins", "insights", "routine_state")


@pytest.fixture
def backend() -> str:
    return "postgres"


@pytest.fixture
def admin(pg_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(pg_url, autocommit=True) as conn:
        yield conn


@contextmanager
def signed_in(pg_url: str, user_id: uuid.UUID | None, role: str = "authenticated"):
    """Run statements the way Supabase runs them for a signed-in user.

    Each use gets its own connection and nothing is committed, so a statement
    that is expected to fail cannot affect the next one.
    """
    conn = psycopg.connect(pg_url)
    try:
        conn.execute(f"set local role {role}")
        if user_id is not None:
            conn.execute("select set_config('request.jwt.claims', %s, true)", [json.dumps({"sub": str(user_id)})])
        yield conn
        conn.rollback()
    finally:
        # Closing without a commit discards the transaction, including a failed one.
        conn.close()


def rejected(pg_url: str, error: type[Exception], statement: str, params: object) -> None:
    """The database itself refuses the statement, whoever sends it."""
    with pytest.raises(error), psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute(statement, params)


def seed(admin: psycopg.Connection, user_id: uuid.UUID) -> None:
    admin.execute("insert into public.routine_state (user_id) values (%s)", [user_id])
    admin.execute("insert into public.profiles (user_id) values (%s)", [user_id])
    admin.execute("insert into public.consents (user_id, consent_type, version) values (%s, 'service', 'v1')", [user_id])
    admin.execute(
        "insert into public.checkins (user_id, local_date, timezone, scale_version, mood) "
        "values (%s, '2026-10-01', 'UTC', 'checkin.v1', 3)", [user_id],
    )
    admin.execute(
        "insert into public.insights (user_id, period_start, period_end, input_version, rule_version, text) "
        "values (%s, '2026-10-01', '2026-10-07', 'abc', 'summary.v1', 'text')", [user_id],
    )


@pytest.fixture
def two_users(admin: psycopg.Connection, new_user: Callable[[], uuid.UUID]) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = new_user(), new_user()
    seed(admin, a)
    seed(admin, b)
    return a, b


def test_row_level_security_is_on_for_every_table(admin: psycopg.Connection) -> None:
    rows = admin.execute(
        "select relname, relrowsecurity from pg_class where relnamespace = 'public'::regnamespace and relname = any(%s)",
        [list(TABLES)],
    ).fetchall()
    assert sorted(rows) == [(table, True) for table in sorted(TABLES)]


def test_a_user_sees_only_their_own_rows(pg_url: str, two_users: tuple[uuid.UUID, uuid.UUID]) -> None:
    a, b = two_users
    with signed_in(pg_url, a) as conn:
        for table in TABLES:
            owners = conn.execute(f"select user_id from public.{table}").fetchall()
            assert owners == [(a,)], table


def test_a_user_cannot_change_or_delete_another_users_rows(
    pg_url: str, admin: psycopg.Connection, two_users: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = two_users
    with signed_in(pg_url, a) as conn:
        assert conn.execute("update public.checkins set mood = 1 where user_id = %s", [b]).rowcount == 0
        assert conn.execute("update public.profiles set timezone = 'Asia/Seoul' where user_id = %s", [b]).rowcount == 0
        assert conn.execute("update public.consents set revoked_at = now() where user_id = %s", [b]).rowcount == 0
        assert conn.execute("update public.insights set feedback = 'useful' where user_id = %s", [b]).rowcount == 0
        for table in TABLES:
            assert conn.execute(f"delete from public.{table} where user_id = %s", [b]).rowcount == 0, table
    assert admin.execute("select mood from public.checkins where user_id = %s", [b]).fetchone() == (3,)


def test_a_user_cannot_insert_rows_for_someone_else(pg_url: str, two_users: tuple[uuid.UUID, uuid.UUID]) -> None:
    a, b = two_users
    statements = [
        "insert into public.checkins (user_id, local_date, timezone, scale_version, mood) values (%s, '2026-09-01', 'UTC', 'v', 1)",
        "insert into public.consents (user_id, consent_type, version) values (%s, 'illustration', 'v1')",
        "insert into public.insights (user_id, period_start, period_end, input_version, rule_version, text) "
        "values (%s, '2026-09-01', '2026-09-07', 'x', 'r', 't')",
    ]
    for statement in statements:
        with pytest.raises(errors.InsufficientPrivilege), signed_in(pg_url, a) as conn:
            conn.execute(statement, [b])


def test_signed_out_and_anonymous_clients_get_nothing(pg_url: str, two_users: tuple[uuid.UUID, uuid.UUID]) -> None:
    with signed_in(pg_url, None) as conn:
        for table in TABLES:
            assert conn.execute(f"select count(*) from public.{table}").fetchone() == (0,), table
    for table in TABLES:
        with pytest.raises(errors.InsufficientPrivilege), signed_in(pg_url, None, role="anon") as conn:
            conn.execute(f"select count(*) from public.{table}")


@pytest.mark.parametrize(
    "statement",
    [
        "update public.checkins set user_id = %(other)s where user_id = %(me)s",
        "update public.checkins set local_date = '2020-01-01' where user_id = %(me)s",
        "update public.checkins set created_at = now() where user_id = %(me)s",
        "update public.profiles set user_id = %(other)s where user_id = %(me)s",
        "update public.consents set version = 'forged' where user_id = %(me)s",
        "update public.consents set granted_at = now() - interval '1 year' where user_id = %(me)s",
        "update public.insights set text = 'rewritten' where user_id = %(me)s",
    ],
)
def test_owners_can_change_only_the_granted_columns(
    pg_url: str, two_users: tuple[uuid.UUID, uuid.UUID], statement: str
) -> None:
    a, b = two_users
    with pytest.raises(errors.InsufficientPrivilege), signed_in(pg_url, a) as conn:
        conn.execute(statement, {"me": a, "other": b})


def test_constraints_reject_values_the_api_would_reject(pg_url: str, two_users: tuple[uuid.UUID, uuid.UUID]) -> None:
    a, _ = two_users
    checkin = (
        "insert into public.checkins (user_id, local_date, timezone, scale_version, {}) "
        "values (%s, '2026-09-01', 'UTC', 'v', {})"
    )
    for column, value in [("mood", 5), ("mood", 0), ("stress", 6), ("connection", 4), ("sleep_quality", 0), ("sleep_hours", 25)]:
        rejected(pg_url, errors.CheckViolation, checkin.format(column, value), [a])
    # The seeded check-in is on 2026-10-01 and the seeded consent is an active 'service' one.
    rejected(pg_url, errors.UniqueViolation, checkin.format("mood", 2).replace("2026-09-01", "2026-10-01"), [a])
    consent = "insert into public.consents (user_id, consent_type, version) values (%s, '{}', 'v2')"
    rejected(pg_url, errors.UniqueViolation, consent.format("service"), [a])
    rejected(pg_url, errors.CheckViolation, consent.format("marketing"), [a])
    rejected(pg_url, errors.CheckViolation, "update public.profiles set budget_amount = 20 where user_id = %s", [a])
    rejected(pg_url, errors.CheckViolation, "update public.profiles set skin_type = 'glowing' where user_id = %s", [a])


def test_removing_the_sign_in_identity_removes_the_users_rows(
    admin: psycopg.Connection, two_users: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = two_users
    admin.execute("delete from auth.users where id = %s", [a])
    for table in TABLES:
        assert admin.execute(f"select count(*) from public.{table} where user_id = %s", [a]).fetchone() == (0,)
        assert admin.execute(f"select count(*) from public.{table} where user_id = %s", [b]).fetchone() == (1,)


def test_the_api_store_acts_as_the_user_and_leaves_no_identity_behind(
    pg_url: str, two_users: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = two_users
    store = PostgresStore(pg_url, max_connections=1)
    try:
        with store._as_user(a) as conn:
            assert conn.execute("select current_user, auth.uid()").fetchone() == {"current_user": "authenticated", "uid": a}
            # Even a statement with no owner filter reaches only this user's rows.
            assert conn.execute("select count(*) as n from public.checkins").fetchone() == {"n": 1}
        with store._pool.connection() as conn:
            leftover = conn.execute(
                "select current_user, current_setting('request.jwt.claims', true) as claims"
            ).fetchone()
        assert leftover["current_user"] != "authenticated"
        assert not leftover["claims"]
    finally:
        store.close()
