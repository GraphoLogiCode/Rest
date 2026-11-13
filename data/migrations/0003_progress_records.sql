-- Private longitudinal observations. Apply after 0002.
-- Small pilot: at most 12 compressed photos per owner through the API.
create table public.progress_records (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('usage', 'photo', 'recommendation', 'feedback')),
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  fingerprint text not null,
  photo_bytes bytea,
  created_at timestamptz not null default now(),
  check ((kind = 'photo' and photo_bytes is not null and octet_length(photo_bytes) <= 2097152)
      or (kind <> 'photo' and photo_bytes is null))
);
create index progress_owner_kind on public.progress_records(user_id, kind, created_at);
alter table public.progress_records enable row level security;
create policy progress_owner on public.progress_records for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
revoke all on public.progress_records from anon, authenticated;
grant select, insert, delete on public.progress_records to authenticated;
