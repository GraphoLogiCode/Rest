# Storage

Where user-owned data is kept. Every method of a store takes the owner's id first and touches only that owner's rows.

- `base.py`: the `Store` interface.
- `memory.py`: keeps data in process memory. For tests and local runs.
- `postgres.py`: Supabase Postgres. Each transaction runs as the `authenticated` role with the owner as `auth.uid()`, so row-level security applies on top of the owner filter in every statement.
- `models.py`: the stored records and the fixed values shared with the API and the migration.
