import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {buildChildTeachingCandidate} from '../lib/aqlevon/child-candidate.js';
import {evaluateChildTeachingCandidate} from '../lib/aqlevon/child-eval.js';

const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const route=fs.readFileSync(path.join(root,'app/api/admin/child-lab/evaluate/route.js'),'utf8');

test('child evaluation scores teaching quality but never authorizes training',()=>{
  const candidate=buildChildTeachingCandidate({
    persona:'باحث',
    lessons:[{text:'تحقق قبل الإجابة'}],
    examples:[
      {input:'أ',child_answer:'x',preferred_answer:'y',persona_snapshot:'باحث'},
      {input:'ب',child_answer:'x',preferred_answer:'z',persona_snapshot:'باحث'},
      {input:'ج',child_answer:'x',preferred_answer:'w',persona_snapshot:'باحث'}
    ],
    trials:[{result:'PASS'},{result:'PASS'},{result:'FAIL'}]
  });
  const e=evaluateChildTeachingCandidate(candidate);
  assert.equal(e.schema,'AQLEVON_CHILD_CANDIDATE_EVAL_V1');
  assert.equal(e.valid,true);
  assert.ok(e.metrics.quality_score>=60);
  assert.equal(e.training_allowed,false);
  assert.equal(e.gpu_allowed,false);
  assert.equal(e.production_weight_write,false);
  assert.equal(e.training_lane_write,false);
  assert.equal(e.worker03_access,false);
});

test('evaluation accepts explicit owner-enabled operational policy',()=>{
  const candidate=buildChildTeachingCandidate({
    persona:'باحث',
    lessons:[{text:'تعلم'}],
    examples:[
      {input:'أ',child_answer:'x',preferred_answer:'y'},
      {input:'ب',child_answer:'x',preferred_answer:'z'},
      {input:'ج',child_answer:'x',preferred_answer:'w'}
    ],
    ownerPolicy:{
      production_weight_write:true,
      training_lane_write:true,
      worker03_access:true,
      automatic_promotion:true,
      gpu_request_allowed:true
    }
  });
  const e=evaluateChildTeachingCandidate(candidate);
  assert.equal(e.valid,true);
  assert.equal(e.production_weight_write,true);
  assert.equal(e.training_lane_write,true);
  assert.equal(e.worker03_access,true);
  assert.equal(e.automatic_promotion,true);
  assert.equal(e.training_allowed,true);
  assert.equal(e.gpu_allowed,true);
});

test('evaluation route is owner-only and side-effect free',()=>{
  assert.match(route,/system_owner/);
  assert.match(route,/OWNER_REQUIRED/);
  assert.match(route,/EVALUATED_ONLY/);
  assert.match(route,/training_started:false/);
  assert.match(route,/gpu_requested:false/);
  assert.match(route,/worker03_access:body\.owner_policy\?\.worker03_access===true/);
  assert.match(route,/owner_policy:body\.owner_policy/);
  assert.doesNotMatch(route,/RunPod|CUDA|torch|trainer|optimizer|LoRA|merge/i);
});


test('evaluation rejects a candidate whose content no longer matches its hash',()=>{
  const candidate=buildChildTeachingCandidate({
    persona:'باحث',
    lessons:[{text:'تحقق قبل الإجابة'}],
    examples:[
      {input:'أ',child_answer:'x',preferred_answer:'y',persona_snapshot:'باحث'},
      {input:'ب',child_answer:'x',preferred_answer:'z',persona_snapshot:'باحث'},
      {input:'ج',child_answer:'x',preferred_answer:'w',persona_snapshot:'باحث'}
    ],
    trials:[{result:'PASS'}]
  });
  const e=evaluateChildTeachingCandidate({...candidate,lessons:['محتوى عُدّل بعد التغليف']});
  assert.equal(e.valid,false);
  assert.ok(e.issues.includes('CANDIDATE_HASH_MISMATCH'));
  assert.equal(e.verdict,'REJECT');
});
