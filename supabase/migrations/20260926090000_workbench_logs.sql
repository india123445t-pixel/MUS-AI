create table if not exists public.workbench_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  tool text not null,
  action text not null,
  level text not null,
  ok boolean not null default false,
  error_class text,
  state text,
  latency_ms integer not null default 0,
  created_at timestamptz not null default now()
);

alter table public.workbench_logs enable row level security;

drop policy if exists workbench_logs_owner_select on public.workbench_logs;
create policy workbench_logs_owner_select
  on public.workbench_logs for select to authenticated
  using (auth.uid() = user_id);

drop policy if exists workbench_logs_owner_insert on public.workbench_logs;
create policy workbench_logs_owner_insert
  on public.workbench_logs for insert to authenticated
  with check (auth.uid() = user_id);

drop policy if exists workbench_logs_owner_update on public.workbench_logs;
create policy workbench_logs_owner_update
  on public.workbench_logs for update to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists workbench_logs_owner_delete on public.workbench_logs;
create policy workbench_logs_owner_delete
  on public.workbench_logs for delete to authenticated
  using (auth.uid() = user_id);

create index if not exists workbench_logs_user_id_idx on public.workbench_logs(user_id);
create index if not exists workbench_logs_created_at_idx on public.workbench_logs(created_at desc);