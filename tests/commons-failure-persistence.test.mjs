import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const migrationUrl=new URL('../supabase/migrations/20260919_aqlevon_commons_failure_accounting.sql',import.meta.url);

test('Commons DB repair preserves failed runtime accounting while status/error stay failed',async()=>{
  const sql=(await readFile(migrationUrl,'utf8')).replace(/\s+/g,' ').trim();
  assert.match(sql,/status=case when p_error is null then 'completed' else 'failed' end/);
  assert.match(sql,/result=coalesce\(p_result,'\{\}'::jsonb\)/);
  assert.match(sql,/error=case when p_error is null then null else left\(p_error,1000\) end/);
  assert.match(sql,/'result',case when v_job\.status in \('completed','failed'\) then v_job\.result else null end/);
  assert.match(sql,/'error',case when v_job\.status in \('failed','expired'\) then v_job\.error else null end/);
  assert.doesNotMatch(sql,/result=case when p_error is null then coalesce\(p_result,'\{\}'::jsonb\) else null end/);
});
