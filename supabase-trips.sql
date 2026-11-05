-- Run once in the Supabase SQL Editor. Users can only read and write their own trips.
create table if not exists public.trips (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  trip jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists trips_user_updated_idx on public.trips (user_id, updated_at desc);
alter table public.trips enable row level security;
grant select, insert, update, delete on public.trips to authenticated;
create policy "Read own trips" on public.trips for select to authenticated using ((select auth.uid()) = user_id);
create policy "Create own trips" on public.trips for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "Update own trips" on public.trips for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "Delete own trips" on public.trips for delete to authenticated using ((select auth.uid()) = user_id);
