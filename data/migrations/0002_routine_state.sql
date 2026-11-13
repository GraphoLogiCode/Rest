-- Apply after 0001. A version guards whole-routine edits from stale clients.
create table public.routine_state (
  user_id uuid primary key references auth.users(id) on delete cascade,
  version bigint not null default 0 check (version >= 0),
  items jsonb not null default '[]'::jsonb check (jsonb_typeof(items) = 'array' and jsonb_array_length(items) <= 100),
  updated_at timestamptz not null default now()
);
alter table public.routine_state enable row level security;
create policy routine_owner on public.routine_state for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
revoke all on public.routine_state from anon, authenticated;
grant select, insert, delete on public.routine_state to authenticated;
grant update (version, items, updated_at) on public.routine_state to authenticated;
