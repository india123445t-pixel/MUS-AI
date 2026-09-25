import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {buildChildTeachingCandidate,evaluateChildCandidate,computeChildCandidateSha256} from '../lib/aqlevon/child-candidate.js';

const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const route=fs.readFileSync(path.join(root,'app/api/admin/child-lab/candidate/route.js'),'utf8');

test('child candidate packages teaching examples without starting training',()=>{
  const c=buildChildTeachingCandidate({
    persona:'باحث',
    lessons:[{text:'تحقق قبل الإجابة'}],
    examples:[{input:'سؤال',child_answer:'خطأ',preferred_answer:'الصحيح',persona_snapshot:'باحث'}],
    trials:[{result:'PASS'},{result:'FAIL'}],
  });
  assert.equal(c.schema,'AQLEVON_CHILD_TEACHING_CANDIDATE_V1');
  assert.equal(c.scope,'child-lab-only');
  assert.equal(c.examples.length,1);
  assert.equal(c.isolation.production_weight_write,false);
  assert.equal(c.isolation.training_lane_write,false);
  assert.equal(c.isolation.worker03_access,false);
  assert.equal(c.isolation.automatic_promotion,false);
  assert.match(c.candidate_sha256,/^[a-f0-9]{64}$/);
  const e=evaluateChildCandidate(c);
  assert.equal(e.valid,true);
  assert.equal(e.recommendation,'EVAL_REQUIRED');
  assert.equal(e.pass_rate,0.5);
});

test('candidate route is owner-only packaging with no GPU or training side effect',()=>{
  assert.match(route,/system_owner/);
  assert.match(route,/OWNER_REQUIRED/);
  assert.match(route,/PACKAGED_ONLY/);
  assert.match(route,/training_started:false/);
  assert.match(route,/gpu_requested:false/);
  assert.match(route,/production_weight_write:false/);
  assert.match(route,/training_lane_write:false/);
  assert.match(route,/worker03_access:false/);
  assert.match(route,/automatic_promotion:false/);
  assert.doesNotMatch(route,/RunPod|CUDA|torch|trainer|optimizer|LoRA|merge/i);
});


test('candidate hash binds teaching content but not volatile creation time',()=>{
  const c=buildChildTeachingCandidate({
    persona:'باحث',
    lessons:[{text:'تحقق قبل الإجابة'}],
    examples:[{input:'سؤال',child_answer:'خطأ',preferred_answer:'الصحيح',persona_snapshot:'باحث'}],
    trials:[{result:'PASS'}],
  });
  assert.equal(computeChildCandidateSha256({...c,created_at:'2099-01-01T00:00:00.000Z'}),c.candidate_sha256);
  const tampered={...c,persona:'تم العبث بالمحتوى'};
  const result=evaluateChildCandidate(tampered);
  assert.equal(result.valid,false);
  assert.ok(result.issues.includes('CANDIDATE_HASH_MISMATCH'));
});
