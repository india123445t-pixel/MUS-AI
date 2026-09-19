-- AQLEVON Commons failure-accounting persistence repair.
-- Keeps failed jobs semantically failed while retaining the worker-supplied
-- runtime accounting envelope for compute-per-verified-success analysis.
-- This migration does NOT authorize or activate paid/public compute.

create or replace function public.aqlevon_commons_complete_job(
  p_worker_token text,
  p_job_id uuid,
  p_result jsonb default null::jsonb,
  p_error text default null::text
)
returns boolean
language plpgsql
security definer
set search_path to 'public', 'extensions', 'pg_catalog'
as $function$
declare
  v_worker_id uuid;
begin
  select id into v_worker_id
  from public.aqlevon_commons_workers
  where token_hash = encode(digest(p_worker_token,'sha256'),'hex')
    and enabled=true
  limit 1;

  if v_worker_id is null then raise exception 'worker_unauthorized'; end if;

  update public.aqlevon_commons_workers
  set last_seen=now()
  where id=v_worker_id;

  update public.aqlevon_commons_jobs
  set status=case when p_error is null then 'completed' else 'failed' end,
      -- Preserve the result envelope for both success and failure.
      -- Failed workers send {ok:false,outcome:'failed',runtime_metrics:{...}}.
      result=coalesce(p_result,'{}'::jsonb),
      error=case when p_error is null then null else left(p_error,1000) end,
      claim_expires_at=null,
      updated_at=now()
  where id=p_job_id
    and claimed_by=v_worker_id
    and status='claimed';

  return found;
end;
$function$;

create or replace function public.aqlevon_commons_job_status(p_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'pg_catalog'
as $function$
declare
  v_job public.aqlevon_commons_jobs%rowtype;
begin
  select * into v_job
  from public.aqlevon_commons_jobs
  where id=p_job_id;

  if not found then return null; end if;

  if v_job.status in ('queued','claimed') and v_job.expires_at <= now() then
    update public.aqlevon_commons_jobs
    set status='expired',updated_at=now()
    where id=p_job_id;
    v_job.status := 'expired';
  end if;

  return jsonb_build_object(
    'id',v_job.id,
    'status',v_job.status,
    -- Failed jobs remain failed, but their accounting envelope is visible
    -- to the status consumer for later cost/efficiency aggregation.
    'result',case when v_job.status in ('completed','failed') then v_job.result else null end,
    'error',case when v_job.status in ('failed','expired') then v_job.error else null end,
    'created_at',v_job.created_at,
    'updated_at',v_job.updated_at,
    'expires_at',v_job.expires_at
  );
end;
$function$;
