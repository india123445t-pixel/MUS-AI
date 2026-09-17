-- AQLEVON identity migration: safe core only.
-- Historical benchmark_results are intentionally excluded because an integrity trigger protects them.

ALTER FUNCTION public.get_mus_runtime_config() RENAME TO get_aqlevon_runtime_config;
ALTER FUNCTION public.get_mus_runtime_lessons(integer) RENAME TO get_aqlevon_runtime_lessons;
ALTER FUNCTION public.get_mus_intelligence_snapshot() RENAME TO get_aqlevon_intelligence_snapshot;

-- Rewrite public functions that still reference the legacy project identity.
DO $$
DECLARE
  r record;
  ddl text;
BEGIN
  FOR r IN
    SELECT p.oid
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.prokind IN ('f','p')
      AND (
        pg_get_functiondef(p.oid) LIKE '%get_mus_%'
        OR pg_get_functiondef(p.oid) LIKE '%MUS AI%'
        OR pg_get_functiondef(p.oid) LIKE '%mus-engine%'
      )
  LOOP
    ddl := pg_get_functiondef(r.oid);
    ddl := replace(ddl, 'get_mus_', 'get_aqlevon_');
    ddl := replace(ddl, 'MUS AI', 'AQLEVON');
    ddl := replace(ddl, 'mus-engine', 'aqlevon-engine');
    EXECUTE ddl;
  END LOOP;
END $$;

ALTER TABLE public.benchmark_cases
  ALTER COLUMN suite SET DEFAULT 'AQLEVON General v0.1';

UPDATE public.benchmark_cases
SET suite = regexp_replace(suite, '^MUS ', 'AQLEVON ')
WHERE suite ~ '^MUS ';

UPDATE public.model_profiles
SET name = regexp_replace(name, '^MUS AI', 'AQLEVON')
WHERE name ~ '^MUS AI';

UPDATE public.training_examples
SET context_snapshot = jsonb_set(context_snapshot, '{created_by}', '"aqlevon-ai-chat"'::jsonb, false)
WHERE context_snapshot->>'created_by' = 'mus-ai-chat';

UPDATE public.model_versions
SET metadata = jsonb_set(
  metadata,
  '{benchmark_suite}',
  to_jsonb(regexp_replace(metadata->>'benchmark_suite', '^MUS ', 'AQLEVON ')),
  false
)
WHERE metadata->>'benchmark_suite' ~ '^MUS ';

UPDATE public.public_chat_logs SET provider = 'aqlevon-engine' WHERE provider = 'mus-engine';
UPDATE public.goal_runs SET provider = 'aqlevon-engine' WHERE provider = 'mus-engine';
UPDATE public.messages SET provider = 'aqlevon-engine' WHERE provider = 'mus-engine';

UPDATE public.control_settings
SET self_hosted_model = regexp_replace(self_hosted_model, '^MUS([ -]|$)', 'AQLEVON\1')
WHERE coalesce(self_hosted_model,'') ~ '^MUS([ -]|$)';