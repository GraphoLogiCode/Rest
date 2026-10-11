"""Read-only readiness checks; never prints the database URL or credentials."""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
url = os.environ.get('DATABASE_URL', '')
if not url:
    raise SystemExit('DATABASE_URL is not configured. Run configure_supabase.py locally.')
expected = {'profiles', 'consents', 'checkins', 'insights', 'routine_state', 'progress_records'}
try:
    with psycopg.connect(url, connect_timeout=10) as conn:
        conn.execute('set transaction read only')
        rows = conn.execute("select c.relname,c.relrowsecurity,has_table_privilege('anon',c.oid,'SELECT') from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname=any(%s)", [sorted(expected)]).fetchall()
        for name, rls, anon in rows:
            print(f'{name}: RLS={rls}; anonymous_read={anon}')
        missing = expected - {row[0] for row in rows}
        if missing: print('Missing tables:', ', '.join(sorted(missing)))
        if missing or any(not row[1] or row[2] for row in rows):
            raise SystemExit('Database readiness check failed.')
        print('Database schema checks passed. Signed-in API smoke tests are still required.')
except psycopg.Error:
    raise SystemExit('Database connection/query failed. Check the private connection settings; credentials were not printed.')
