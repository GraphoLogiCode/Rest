-- Rest migration 0001: profiles, consents, check-ins, insights.
--
-- Target: Supabase Postgres. Expects auth.users, auth.uid(), and the anon and
-- authenticated roles. Every table is owned by one user and protected twice:
-- row-level security limits rows to their owner, and column grants limit what
-- an owner may change.

create table public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  timezone text not null default 'UTC',
  goals text[] not null default '{}',
  skin_type text check (skin_type in ('dry', 'normal', 'combination', 'oily')),
  concerns text[],
  -- null means not answered; an empty array means the user reported none.
  ingredient_exclusions text[],
  budget_amount numeric(10, 2) check (budget_amount >= 0),
  budget_currency text check (budget_currency ~ '^[A-Z]{3}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((budget_amount is null) = (budget_currency is null))
);

create table public.consents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  consent_type text not null
    check (consent_type in ('service', 'model_training', 'photo_storage', 'illustration')),
  version text not null,
  granted_at timestamptz not null default now(),
  revoked_at timestamptz,
  check (revoked_at is null or revoked_at >= granted_at)
);

-- A user has at most one active consent of each type; history rows stay.
create unique index consents_one_active
  on public.consents (user_id, consent_type)
  where revoked_at is null;

create table public.checkins (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  local_date date not null,
  -- The user's timezone when the check-in was made. Timestamps are UTC.
  timezone text not null,
  scale_version text not null,
  sleep_hours numeric(3, 1) check (sleep_hours between 0 and 24),
  sleep_quality smallint check (sleep_quality between 1 and 5),
  mood smallint check (mood between 1 and 4),
  stress smallint check (stress between 1 and 5),
  connection smallint check (connection between 1 and 3),
  note text check (char_length(note) <= 2000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, local_date)
);

create table public.insights (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  period_start date not null,
  period_end date not null,
  input_version text not null,
  rule_version text not null,
  text text not null,
  feedback text check (feedback in ('useful', 'not_useful')),
  feedback_at timestamptz,
  created_at timestamptz not null default now(),
  check (period_end >= period_start),
  unique (user_id, period_start, period_end, input_version, rule_version)
);

alter table public.profiles enable row level security;
alter table public.consents enable row level security;
alter table public.checkins enable row level security;
alter table public.insights enable row level security;

create policy profiles_owner on public.profiles for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy consents_owner on public.consents for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy checkins_owner on public.checkins for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy insights_owner on public.insights for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- Supabase grants every role full access to new public tables by default.
-- Start from nothing and grant only what an owner needs.
revoke all on public.profiles, public.consents, public.checkins, public.insights
  from anon, authenticated;

grant select, insert, delete on public.profiles to authenticated;
grant update (timezone, goals, skin_type, concerns, ingredient_exclusions,
              budget_amount, budget_currency, updated_at)
  on public.profiles to authenticated;

grant select, insert, delete on public.consents to authenticated;
grant update (revoked_at) on public.consents to authenticated;

grant select, insert, delete on public.checkins to authenticated;
grant update (sleep_hours, sleep_quality, mood, stress, connection, note, updated_at)
  on public.checkins to authenticated;

grant select, insert, delete on public.insights to authenticated;
grant update (feedback, feedback_at) on public.insights to authenticated;
