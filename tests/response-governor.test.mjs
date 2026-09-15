import test from 'node:test';
import assert from 'node:assert/strict';
import { governResponse } from '../lib/mus/response-governor.js';

test('current claim with INCONCLUSIVE evidence receives deterministic evidence qualification',()=>{
  const out=governResponse({
    text:'The current price is 10.',
    contract:{language:'other',external_evidence_required:true,domains:['research'],externally_actionable:false,high_consequence:false},
    verification:{required:true,result:'INCONCLUSIVE'},deterministic:{},
  });
  assert.ok(out.text.startsWith('Evidence note:'));
});

test('actionable request cannot look executed without postcondition evidence',()=>{
  const out=governResponse({
    text:'Done.',
    contract:{language:'ar',external_evidence_required:false,domains:['communication'],externally_actionable:true,high_consequence:true},
    verification:{required:true,result:'INCONCLUSIVE'},deterministic:{postconditionEvidence:false},
  });
  assert.ok(out.text.includes('لم تنفّذ الإجراء المطلوب'));
});

test('verified low-risk answer receives no epistemic boilerplate',()=>{
  const out=governResponse({
    text:'A binary tree is a tree where each node has at most two children.',
    contract:{language:'other',external_evidence_required:false,domains:['general'],externally_actionable:false,high_consequence:false},
    verification:{required:false,result:null},deterministic:{},
  });
  assert.equal(out.text,'A binary tree is a tree where each node has at most two children.');
});
