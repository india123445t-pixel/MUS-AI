-- AQLEVON AI Behavioral Operating System v1
-- Additive migration only. It does not modify existing public chat/control tables.

create extension if not exists pgcrypto;

create table if not exists public.aqlevon_requests (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  session_id uuid,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.aqlevon_principal_bindings (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  external_principal_ref text,
  session_ref text,
  scope jsonb not null default '{}'::jsonb,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','REVOKED','EXPIRED')),
  valid_from timestamptz not null default now(),
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.aqlevon_tasks (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  request_id uuid references public.aqlevon_requests(id) on delete set null,
  phase text not null default 'OPEN' check (phase in ('OPEN','READY','RUNNING','WAITING','RECONCILING','CLOSED')),
  outcome text not null default 'NONE' check (outcome in ('NONE','SUCCESS','PARTIAL','FAILED','CANCELLED','UNKNOWN')),
  title text,
  scope jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((phase='CLOSED' and outcome<>'NONE') or (phase<>'CLOSED' and outcome='NONE'))
);

create table if not exists public.aqlevon_task_contracts (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid not null references public.aqlevon_tasks(id) on delete cascade,
  version integer not null check (version > 0),
  contract jsonb not null,
  contract_digest text not null,
  supersedes_id uuid references public.aqlevon_task_contracts(id),
  created_at timestamptz not null default now(),
  unique(task_id,version),
  unique(task_id,contract_digest)
);

create table if not exists public.aqlevon_durable_constraints (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  constraint_id uuid not null,
  version integer not null check (version > 0),
  scope_ref text not null,
  applicability jsonb not null default '{}'::jsonb,
  rule_spec jsonb not null,
  rule_hash text not null,
  authority_basis jsonb not null,
  principal_binding_id uuid references public.aqlevon_principal_bindings(id),
  confirmation_ref uuid,
  policy_ref text,
  status text not null check (status in ('ACTIVE','SUPERSEDED','REVOKED')),
  valid_from timestamptz not null default now(),
  expires_at timestamptz,
  supersedes_ref uuid references public.aqlevon_durable_constraints(id),
  superseded_by_ref uuid references public.aqlevon_durable_constraints(id),
  revoked_at timestamptz,
  state_version bigint not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id,constraint_id,version)
);
create unique index if not exists aqlevon_durable_constraints_one_active_lineage
  on public.aqlevon_durable_constraints(owner_id,constraint_id)
  where status='ACTIVE';
create index if not exists aqlevon_durable_constraints_scope_active_idx
  on public.aqlevon_durable_constraints(owner_id,scope_ref,status);

create table if not exists public.aqlevon_action_intents (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid not null references public.aqlevon_tasks(id) on delete cascade,
  contract_id uuid not null references public.aqlevon_task_contracts(id),
  semantic_action text not null,
  canonical_resource jsonb not null,
  canonical_parameters jsonb not null,
  parameter_digest text not null,
  effective_capabilities text[] not null default '{}',
  idempotency_identity text,
  auth_state text not null default 'PROPOSED' check (auth_state in ('PROPOSED','DENIED','AWAITING_CONFIRMATION','AUTHORIZED','RETIRED')),
  created_at timestamptz not null default now()
);

create table if not exists public.aqlevon_confirmation_records (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  action_intent_id uuid not null references public.aqlevon_action_intents(id) on delete cascade,
  principal_binding_id uuid references public.aqlevon_principal_bindings(id),
  confirmation_type text not null,
  exact_binding_digest text not null,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.aqlevon_permits (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid not null references public.aqlevon_tasks(id) on delete cascade,
  contract_id uuid not null references public.aqlevon_task_contracts(id),
  action_intent_id uuid not null references public.aqlevon_action_intents(id) on delete cascade,
  principal_binding_id uuid not null references public.aqlevon_principal_bindings(id),
  exact_resource jsonb not null,
  exact_parameters jsonb not null,
  exact_binding_digest text not null,
  constraint_refs jsonb not null default '[]'::jsonb,
  constraint_set_digest text not null,
  tool_spec_ref jsonb,
  confirmation_id uuid references public.aqlevon_confirmation_records(id),
  status text not null default 'ACTIVE' check (status in ('ACTIVE','CONSUMED','REVOKED','EXPIRED')),
  valid_from timestamptz not null default now(),
  expires_at timestamptz,
  consumed_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists aqlevon_permits_active_idx on public.aqlevon_permits(owner_id,status,action_intent_id);

create table if not exists public.aqlevon_action_attempts (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid not null references public.aqlevon_tasks(id) on delete cascade,
  action_intent_id uuid not null references public.aqlevon_action_intents(id),
  permit_id uuid not null references public.aqlevon_permits(id),
  attempt_no integer not null check (attempt_no > 0),
  phase text not null default 'QUEUED' check (phase in ('QUEUED','IN_FLIGHT','RECONCILING','CLOSED')),
  outcome text not null default 'NONE' check (outcome in ('NONE','SUCCESS','FAILURE','PARTIAL','UNKNOWN','CANCELLED')),
  dispatch_claim text unique,
  provider_operation_id text,
  started_at timestamptz,
  closed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(action_intent_id,attempt_no),
  check ((phase='CLOSED' and outcome<>'NONE') or (phase<>'CLOSED' and outcome='NONE'))
);

create table if not exists public.aqlevon_action_receipts (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  action_attempt_id uuid not null unique references public.aqlevon_action_attempts(id) on delete cascade,
  action_intent_id uuid not null references public.aqlevon_action_intents(id),
  permit_id uuid not null references public.aqlevon_permits(id),
  executor_identity text not null,
  observed_resource jsonb,
  request_digest text,
  transport_status jsonb not null default '{}'::jsonb,
  executor_reported_outcome text,
  provider_operation_id text,
  emitted_at timestamptz not null default now()
);

create table if not exists public.aqlevon_artifacts (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid references public.aqlevon_tasks(id) on delete set null,
  kind text not null,
  version text,
  lifecycle text not null default 'DRAFT' check (lifecycle in ('DRAFT','AVAILABLE','QUARANTINED','SUPERSEDED','DELETED')),
  content_digest text,
  provenance jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.aqlevon_evidence_bindings (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  subject_type text not null check (subject_type in ('ACTION_ATTEMPT','ARTIFACT','CLAIM','TASK_CRITERION')),
  subject_ref text not null,
  criterion_id text not null,
  criterion_version text not null,
  source_type text not null,
  source_ref text,
  artifact_id uuid references public.aqlevon_artifacts(id),
  selector jsonb,
  source_digest text,
  observed_at timestamptz,
  source_as_of timestamptz,
  provenance jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.aqlevon_verification_states (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  subject_type text not null check (subject_type in ('ACTION_ATTEMPT','ARTIFACT','CLAIM','TASK_CRITERION')),
  subject_ref text not null,
  criterion_id text not null,
  criterion_version text not null,
  observation_version integer not null default 1,
  phase text not null default 'PENDING' check (phase in ('PENDING','RUNNING','RESOLVED')),
  result text check (result in ('VERIFIED','REFUTED','INCONCLUSIVE','CONFLICTING')),
  evidence_binding_ids uuid[] not null default '{}',
  reasons jsonb not null default '[]'::jsonb,
  observed_at timestamptz,
  created_at timestamptz not null default now(),
  check ((phase='RESOLVED' and result is not null) or (phase<>'RESOLVED' and result is null)),
  unique(owner_id,subject_type,subject_ref,criterion_id,criterion_version,observation_version)
);

create table if not exists public.aqlevon_claims (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid references public.aqlevon_tasks(id) on delete set null,
  proposition text not null,
  proposition_digest text not null,
  provenance_class text not null check (provenance_class in ('USER_STATED','SYSTEM_OBSERVED','VERIFIED','INFERRED','ASSUMED','PREFERENCE','IMPORTED_UNTRUSTED','MODEL_PROSE')),
  created_at timestamptz not null default now()
);

create table if not exists public.aqlevon_responses (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid references public.aqlevon_tasks(id) on delete set null,
  response_type text not null check (response_type in ('ANSWER','CLARIFICATION','APPROVAL_REQUEST','STATUS','FINAL')),
  body text not null,
  metadata jsonb not null default '{}'::jsonb,
  emitted_at timestamptz not null default now()
);

create table if not exists public.aqlevon_audit_events (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid references public.aqlevon_tasks(id) on delete set null,
  event_type text not null,
  subject_type text,
  subject_ref text,
  event_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists aqlevon_audit_events_task_created_idx on public.aqlevon_audit_events(owner_id,task_id,created_at desc);

-- Trusted tool/capability registry contracts. These are NOT runtime authority tokens.
create table if not exists public.aqlevon_tool_specs (
  tool_id text not null,
  version text not null,
  spec_digest text not null,
  lifecycle text not null check (lifecycle in ('APPROVED','ACTIVE','WITHDRAWN','QUARANTINED')),
  spec jsonb not null,
  created_at timestamptz not null default now(),
  primary key(tool_id,version)
);

create table if not exists public.aqlevon_capability_specs (
  capability_id text not null,
  version text not null,
  spec_digest text not null,
  spec jsonb not null,
  created_at timestamptz not null default now(),
  primary key(capability_id,version)
);

-- RLS: owner-scoped canonical runtime state. Service role can manage registry contracts.
do $$
declare t text;
begin
  foreach t in array array[
    'aqlevon_requests','aqlevon_principal_bindings','aqlevon_tasks','aqlevon_task_contracts','aqlevon_durable_constraints',
    'aqlevon_action_intents','aqlevon_confirmation_records','aqlevon_permits','aqlevon_action_attempts','aqlevon_action_receipts',
    'aqlevon_artifacts','aqlevon_evidence_bindings','aqlevon_verification_states','aqlevon_claims','aqlevon_responses','aqlevon_audit_events'
  ] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('drop policy if exists %I on public.%I',t||'_owner_all',t);
    execute format('create policy %I on public.%I for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid())',t||'_owner_all',t);
  end loop;
end $$;

alter table public.aqlevon_tool_specs enable row level security;
alter table public.aqlevon_capability_specs enable row level security;

-- No client-side policies for registry contracts: only service-role / trusted backend paths should mutate/read them.

create or replace function public.aqlevon_active_constraints(p_scope_ref text)
returns setof public.aqlevon_durable_constraints
language sql
stable
security invoker
set search_path=public
as $$
  select *
  from public.aqlevon_durable_constraints
  where owner_id=auth.uid()
    and scope_ref=p_scope_ref
    and status='ACTIVE'
    and valid_from<=now()
    and (expires_at is null or expires_at>now())
  order by constraint_id,version desc;
$$;
