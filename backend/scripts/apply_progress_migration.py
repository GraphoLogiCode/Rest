"""Apply only the new additive progress table to the configured Rest project."""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg
root = Path(__file__).resolve().parents[2]
load_dotenv(root / 'backend/.env')
if os.environ.get('SUPABASE_URL') != 'https://byrndjhgzusfjdgjfbev.supabase.co':
    raise SystemExit('Unexpected project. No changes made.')
try:
    with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=10) as conn:
        conn.execute("select pg_advisory_xact_lock(hashtextextended('rest-progress-migration',0))")
        if conn.execute("select to_regclass('public.routine_state') is null").fetchone()[0]:
            raise SystemExit('Existing routine migration is missing. No changes made.')
        if conn.execute("select to_regclass('public.progress_records') is not null").fetchone()[0]:
            print('Progress table already exists; no migration applied.')
        else:
            conn.execute((root / 'data/migrations/0003_progress_records.sql').read_text())
            print('Applied additive progress migration in one transaction.')
except psycopg.Error:
    raise SystemExit('Migration failed and rolled back. Check private database configuration; no credentials printed.')
