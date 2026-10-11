# Migrations

Database migrations for the Supabase Postgres database, applied in filename order.

| File | Creates |
|---|---|
| [0001_profiles_consents_checkins_insights.sql](0001_profiles_consents_checkins_insights.sql) | `profiles`, `consents`, `checkins`, `insights`, with row-level security and column grants |

Each table is limited to its owner by a row-level security policy, and column grants limit what an owner may change. The checks are in `backend/tests/test_database.py`.

Apply `0002_routine_state.sql` after `0001` for per-account routine persistence, optimistic version checks, and row-level security. The account-setup chat applied 0001–0002 to the Rest Supabase project. Verify current state before migration changes.

Apply `0003_progress_records.sql` next for private photos, product-use reports, recommendation snapshots and feedback. It was applied transactionally to the Rest project on 2026-10-11 and verified to have RLS enabled and no anonymous SELECT privilege.
