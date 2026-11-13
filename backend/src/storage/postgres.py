import json
from collections.abc import Iterator
from contextlib import contextmanager, asynccontextmanager
from datetime import date
from typing import Any
from uuid import UUID

from psycopg import Connection, AsyncConnection, sql
from psycopg.errors import LockNotAvailable
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.storage.base import CheckInExists, check_checkin_values, check_profile_changes
from src.storage.models import CheckIn, Consent, Insight, Profile, column_names


def _columns(model: type) -> sql.Composed:
    return sql.SQL(", ").join(sql.Identifier(name) for name in column_names(model))


PROFILE_COLUMNS = _columns(Profile)
CONSENT_COLUMNS = _columns(Consent)
CHECKIN_COLUMNS = _columns(CheckIn)
INSIGHT_COLUMNS = _columns(Insight)


def _assignments(changes: dict[str, Any]) -> sql.Composed:
    return sql.SQL(", ").join(
        sql.SQL("{} = {}").format(sql.Identifier(name), sql.Placeholder(name)) for name in changes
    )


class PostgresStore:
    """Stores user data in Supabase Postgres.

    Ownership is enforced twice. Every statement filters on the owner's id,
    and each transaction drops to the `authenticated` role with the owner as
    `auth.uid()`, so row-level security still applies even though the
    connection itself is privileged.
    """

    def __init__(self, database_url: str, *, max_connections: int = 5):
        self._database_url = database_url
        self._pool = ConnectionPool(
            database_url,
            min_size=1,
            max_size=max_connections,
            # prepare_threshold=None keeps this compatible with Supabase's transaction pooler.
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,
        )

    @asynccontextmanager
    async def progress_owner_lock(self, user_id):
        # A separate transaction stays open while the API performs its shorter
        # store transactions. The distinct lock key avoids reentrant deadlock
        # with create_progress's quota lock. Transaction locks also work through
        # Supabase transaction pooling and release after process/connection loss.
        from src.errors import ApiError
        try:
            async with await AsyncConnection.connect(self._database_url, connect_timeout=10) as conn:
                await conn.execute("set local lock_timeout = '10s'")
                await conn.execute('select pg_advisory_xact_lock(hashtextextended(%s, 1))', [str(user_id)])
                yield
        except LockNotAvailable as exc:
            raise ApiError(503, 'account_busy', 'Another account operation is in progress. Try again shortly.') from exc

    @contextmanager
    def _as_user(self, user_id: UUID) -> Iterator[Connection]:
        claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
        with self._pool.connection() as conn, conn.transaction():
            conn.execute("set local role authenticated")
            conn.execute(
                "select set_config('request.jwt.claim.sub', %s, true), set_config('request.jwt.claims', %s, true)",
                [str(user_id), claims],
            )
            yield conn

    # Profiles

    def _ensure_profile(self, conn: Connection, user_id: UUID) -> None:
        conn.execute(
            "insert into public.profiles (user_id) values (%s) on conflict (user_id) do nothing", [user_id]
        )

    def _select_profile(self, conn: Connection, user_id: UUID) -> Profile:
        query = sql.SQL("select {} from public.profiles where user_id = %s").format(PROFILE_COLUMNS)
        return Profile(**conn.execute(query, [user_id]).fetchone())

    def get_or_create_profile(self, user_id: UUID) -> Profile:
        with self._as_user(user_id) as conn:
            self._ensure_profile(conn, user_id)
            return self._select_profile(conn, user_id)

    def update_profile(self, user_id: UUID, changes: dict[str, Any]) -> Profile:
        check_profile_changes(changes)
        with self._as_user(user_id) as conn:
            self._ensure_profile(conn, user_id)
            if changes:
                query = sql.SQL(
                    "update public.profiles set {}, updated_at = now() where user_id = %(user_id)s"
                ).format(_assignments(changes))
                conn.execute(query, {**changes, "user_id": user_id})
            return self._select_profile(conn, user_id)

    # Consents

    def list_consents(self, user_id: UUID) -> list[Consent]:
        query = sql.SQL(
            "select {} from public.consents where user_id = %s order by granted_at desc"
        ).format(CONSENT_COLUMNS)
        with self._as_user(user_id) as conn:
            return [Consent(**row) for row in conn.execute(query, [user_id])]

    def _active(self, conn: Connection, user_id: UUID, consent_type: str) -> Consent | None:
        query = sql.SQL(
            "select {} from public.consents where user_id = %s and consent_type = %s and revoked_at is null"
        ).format(CONSENT_COLUMNS)
        row = conn.execute(query, [user_id, consent_type]).fetchone()
        return Consent(**row) if row else None

    def active_consent(self, user_id: UUID, consent_type: str) -> Consent | None:
        with self._as_user(user_id) as conn:
            return self._active(conn, user_id, consent_type)

    def _revoke(self, conn: Connection, user_id: UUID, consent_type: str) -> Consent | None:
        query = sql.SQL(
            "update public.consents set revoked_at = now() "
            "where user_id = %s and consent_type = %s and revoked_at is null returning {}"
        ).format(CONSENT_COLUMNS)
        row = conn.execute(query, [user_id, consent_type]).fetchone()
        return Consent(**row) if row else None

    def grant_consent(self, user_id: UUID, consent_type: str, version: str) -> Consent:
        with self._as_user(user_id) as conn:
            active = self._active(conn, user_id, consent_type)
            if active is not None:
                if active.version == version:
                    return active
                self._revoke(conn, user_id, consent_type)
            query = sql.SQL(
                "insert into public.consents (user_id, consent_type, version) values (%s, %s, %s) returning {}"
            ).format(CONSENT_COLUMNS)
            return Consent(**conn.execute(query, [user_id, consent_type, version]).fetchone())

    def revoke_consent(self, user_id: UUID, consent_type: str) -> Consent | None:
        with self._as_user(user_id) as conn:
            return self._revoke(conn, user_id, consent_type)

    # Check-ins

    def create_checkin(
        self, user_id: UUID, local_date: date, timezone: str, scale_version: str, values: dict[str, Any]
    ) -> CheckIn:
        check_checkin_values(values)
        row_values = {
            "user_id": user_id, "local_date": local_date, "timezone": timezone,
            "scale_version": scale_version, **values,
        }
        insert = sql.SQL(
            "insert into public.checkins ({}) values ({}) "
            "on conflict (user_id, local_date) do nothing returning {}"
        ).format(
            sql.SQL(", ").join(sql.Identifier(name) for name in row_values),
            sql.SQL(", ").join(sql.Placeholder(name) for name in row_values),
            CHECKIN_COLUMNS,
        )
        with self._as_user(user_id) as conn:
            row = conn.execute(insert, row_values).fetchone()
            if row is not None:
                return CheckIn(**row)
            existing = conn.execute(
                "select id from public.checkins where user_id = %s and local_date = %s", [user_id, local_date]
            ).fetchone()
        raise CheckInExists(existing["id"])

    def get_checkin(self, user_id: UUID, checkin_id: UUID) -> CheckIn | None:
        query = sql.SQL("select {} from public.checkins where id = %s and user_id = %s").format(CHECKIN_COLUMNS)
        with self._as_user(user_id) as conn:
            row = conn.execute(query, [checkin_id, user_id]).fetchone()
        return CheckIn(**row) if row else None

    def update_checkin(self, user_id: UUID, checkin_id: UUID, changes: dict[str, Any]) -> CheckIn | None:
        check_checkin_values(changes)
        if not changes:
            return self.get_checkin(user_id, checkin_id)
        query = sql.SQL(
            "update public.checkins set {}, updated_at = now() "
            "where id = %(id)s and user_id = %(user_id)s returning {}"
        ).format(_assignments(changes), CHECKIN_COLUMNS)
        with self._as_user(user_id) as conn:
            row = conn.execute(query, {**changes, "id": checkin_id, "user_id": user_id}).fetchone()
        return CheckIn(**row) if row else None

    def list_checkins(self, user_id: UUID, start: date | None = None, end: date | None = None) -> list[CheckIn]:
        query = sql.SQL(
            "select {} from public.checkins where user_id = %(user_id)s "
            "and (%(start)s::date is null or local_date >= %(start)s::date) "
            "and (%(end)s::date is null or local_date <= %(end)s::date) "
            "order by local_date desc"
        ).format(CHECKIN_COLUMNS)
        with self._as_user(user_id) as conn:
            rows = conn.execute(query, {"user_id": user_id, "start": start, "end": end}).fetchall()
        return [CheckIn(**row) for row in rows]

    # Insights

    def save_insight(
        self, user_id: UUID, period_start: date, period_end: date, input_version: str, rule_version: str, text: str
    ) -> Insight:
        key = [user_id, period_start, period_end, input_version, rule_version]
        select = sql.SQL(
            "select {} from public.insights where user_id = %s and period_start = %s "
            "and period_end = %s and input_version = %s and rule_version = %s"
        ).format(INSIGHT_COLUMNS)
        with self._as_user(user_id) as conn:
            conn.execute(
                "insert into public.insights (user_id, period_start, period_end, input_version, rule_version, text) "
                "values (%s, %s, %s, %s, %s, %s) on conflict do nothing",
                [*key, text],
            )
            return Insight(**conn.execute(select, key).fetchone())

    def list_insights(self, user_id: UUID) -> list[Insight]:
        query = sql.SQL(
            "select {} from public.insights where user_id = %s order by created_at desc"
        ).format(INSIGHT_COLUMNS)
        with self._as_user(user_id) as conn:
            return [Insight(**row) for row in conn.execute(query, [user_id])]

    def set_insight_feedback(self, user_id: UUID, insight_id: UUID, feedback: str) -> Insight | None:
        query = sql.SQL(
            "update public.insights set feedback = %s, feedback_at = now() "
            "where id = %s and user_id = %s returning {}"
        ).format(INSIGHT_COLUMNS)
        with self._as_user(user_id) as conn:
            row = conn.execute(query, [feedback, insight_id, user_id]).fetchone()
        return Insight(**row) if row else None

    def get_routine(self, user_id: UUID) -> dict:
        with self._as_user(user_id) as conn:
            row = conn.execute("select items, version from public.routine_state where user_id = %s", [user_id]).fetchone()
            return dict(row) if row else {"items": [], "version": 0}

    def save_routine(self, user_id: UUID, version: int, items: list[dict]) -> dict | None:
        with self._as_user(user_id) as conn:
            conn.execute("insert into public.routine_state(user_id) values (%s) on conflict do nothing", [user_id])
            row = conn.execute("update public.routine_state set items=%s::jsonb, version=version+1, updated_at=now() where user_id=%s and version=%s returning items, version", [json.dumps(items), user_id, version]).fetchone()
            return dict(row) if row else None

    # Private progress observations. Lock per owner to keep quotas atomic.

    def create_progress(self, user_id, entry_id, kind, payload, fingerprint, image=None):
        from src.errors import ApiError
        with self._as_user(user_id) as conn:
            conn.execute('select pg_advisory_xact_lock(hashtextextended(%s, 0))', [str(user_id)])
            old=conn.execute('select id, kind, payload, created_at, fingerprint from public.progress_records where user_id=%s and id=%s', [user_id, entry_id]).fetchone()
            if old:
                if old.pop('fingerprint') != fingerprint or old['kind'] != kind:
                    raise ApiError(409, 'entry_conflict', 'Use a new entry ID for a different report.')
                return self._public_progress(old)
            count=conn.execute('select count(*) as n from public.progress_records where user_id=%s and kind=%s', [user_id, kind]).fetchone()['n']
            if count >= (12 if kind=='photo' else 1000):
                raise ApiError(409, 'storage_limit', 'Your pilot storage limit is reached. Export or delete older entries first.')
            row=conn.execute('insert into public.progress_records(id,user_id,kind,payload,fingerprint,photo_bytes) values (%s,%s,%s,%s::jsonb,%s,%s) on conflict (id) do nothing returning id,kind,payload,created_at',
                             [entry_id,user_id,kind,json.dumps(payload),fingerprint,image]).fetchone()
            if row is None:
                raise ApiError(409, 'entry_conflict', 'Use a new entry ID for a different report.')
            return self._public_progress(row)

    @staticmethod
    def _public_progress(row):
        return {**row, 'id':str(row['id']), 'created_at':row['created_at'].isoformat()}

    def list_progress(self, user_id, kind):
        with self._as_user(user_id) as conn:
            return [self._public_progress(r) for r in conn.execute('select id,kind,payload,created_at from public.progress_records where user_id=%s and kind=%s order by created_at desc,id', [user_id,kind])]

    def progress_image(self, user_id, entry_id):
        with self._as_user(user_id) as conn:
            row=conn.execute("select photo_bytes from public.progress_records where user_id=%s and id=%s and kind='photo'", [user_id, entry_id]).fetchone()
            return bytes(row['photo_bytes']) if row else None

    def delete_progress(self, user_id, entry_id):
        with self._as_user(user_id) as conn:
            return conn.execute('delete from public.progress_records where user_id=%s and id=%s', [user_id,entry_id]).rowcount > 0

    def purge_photos(self, user_id):
        with self._as_user(user_id) as conn:
            return conn.execute("delete from public.progress_records where user_id=%s and kind='photo'", [user_id]).rowcount

    # Account

    def delete_user_data(self, user_id: UUID) -> dict[str, int]:
        counts: dict[str, int] = {}
        with self._as_user(user_id) as conn:
            for table in ("progress_records", "insights", "checkins", "routine_state", "consents", "profiles"):
                query = sql.SQL("delete from public.{} where user_id = %s").format(sql.Identifier(table))
                counts[table] = conn.execute(query, [user_id]).rowcount
        return counts

    def close(self) -> None:
        self._pool.close()
