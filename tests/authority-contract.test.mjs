import test from 'node:test';
import assert from 'node:assert/strict';
import { createTrustedRegistry, readQualification } from '../lib/aqlevon/tool-registry.js';
import { canonicalResource, createActionIntent, issuePermit, preDispatchCheck } from '../lib/aqlevon/authority.js';
import { transitionActionAttempt, transitionTask, transitionVerification } from '../lib/aqlevon/state-machines.js';
import { createActionReceipt, receiptProvesWorldState } from '../lib/aqlevon/receipts.js';
import { buildModelContext, criticalContextManifest, validateCompaction } from '../lib/aqlevon/context.js';

const tool=()=>createTrustedRegistry({toolSpecs:[{
  tool_id:'repo.write',version:'1',provider:'github',adapter_identity:'github-adapter@1',lifecycle:'ACTIVE',
  capabilities:['READ','WRITE'],resource_types:['repository'],consequential_parameters:['path','content'],
  read_qualification:{evidence_ref:'conformance:repo-read-v1'},
}]}).getTool('repo.write','1');
const principal={id:'p1',status:'ACTIVE'};
const contract={contract_id:'c1'};
const resource={provider:'github',tenant:'owner',project:'AQLEVON-AI',environment:'production',resource_id:'repo-123'};

test('canonical resource requires exact tenant/environment/resource identity',()=>{
  assert.throws(()=>canonicalResource({provider:'github',resource_id:'repo-123'}));
  assert.equal(canonicalResource(resource).tenant,'owner');
});

test('Permit binds exact parameters and pre-dispatch drift fails closed',()=>{
  const intent=createActionIntent({task_id:'t1',contract_id:'c1',semantic_action:'update-file',resource,parameters:{path:'README.md',content:'x'},capabilities:['WRITE']});
  const permit=issuePermit({principal,taskContract:contract,intent,toolSpec:tool(),constraints:[]});
  assert.equal(preDispatchCheck({permit,principal,taskContract:contract,intent,toolSpec:tool(),constraints:[]}).allowed,true);
  const drift={...intent,canonical_parameters:{path:'README.md',content:'different'}};
  const result=preDispatchCheck({permit,principal,taskContract:contract,intent:drift,toolSpec:tool(),constraints:[]});
  assert.equal(result.allowed,false);
  assert.ok(result.reasons.some(x=>x.includes('parameters changed')));
});

test('active DurableConstraint denial prevents Permit issuance',()=>{
  const intent=createActionIntent({task_id:'t1',contract_id:'c1',semantic_action:'update-file',resource,parameters:{path:'x'},capabilities:['WRITE']});
  const constraints=[{constraint_id:'dc1',version:1,status:'ACTIVE',scope_ref:'AQLEVON-AI',applicability:{tenant:'owner',project:'AQLEVON-AI',capabilities:['WRITE']},rule_hash:'h',rule_spec:{effect:'DENY'}}];
  assert.throws(()=>issuePermit({principal,taskContract:contract,intent,toolSpec:tool(),constraints}),/denies/);
});

test('changing applicable DurableConstraint set invalidates unconsumed Permit at dispatch',()=>{
  const intent=createActionIntent({task_id:'t1',contract_id:'c1',semantic_action:'update-file',resource,parameters:{path:'x'},capabilities:['WRITE']});
  const permit=issuePermit({principal,taskContract:contract,intent,toolSpec:tool(),constraints:[]});
  const newConstraint={constraint_id:'dc2',version:1,status:'ACTIVE',scope_ref:'AQLEVON-AI',applicability:{project:'AQLEVON-AI'},rule_hash:'h2',rule_spec:{effect:'REQUIRE'}};
  const check=preDispatchCheck({permit,principal,taskContract:contract,intent,toolSpec:tool(),constraints:[newConstraint]});
  assert.equal(check.allowed,false);
  assert.ok(check.reasons.some(x=>x.includes('DurableConstraint')));
});

test('READ qualification fails when consequential hidden effect exists',()=>{
  const registry=createTrustedRegistry({toolSpecs:[{tool_id:'weird.read',version:'1',provider:'x',adapter_identity:'a',capabilities:['READ'],hidden_effects:['WRITE'],read_qualification:{evidence_ref:'e'}}]});
  const q=readQualification(registry.getTool('weird.read','1'));
  assert.equal(q.qualified,false);
});

test('ActionReceipt binding never becomes VerificationState truth',()=>{
  const intent=createActionIntent({task_id:'t1',contract_id:'c1',semantic_action:'update-file',resource,parameters:{path:'x'},capabilities:['WRITE']});
  const permit=issuePermit({principal,taskContract:contract,intent,toolSpec:tool(),constraints:[]});
  const attempt={id:'a1',action_intent_id:intent.id,permit_id:permit.id,phase:'IN_FLIGHT',outcome:'NONE'};
  const receipt=createActionReceipt({attempt,intent,permit,executor_identity:'executor-1',executor_reported_outcome:'SUCCESS'});
  assert.equal(receipt.verification_result,null);
  assert.equal(receiptProvesWorldState(receipt),false);
});

test('frozen state machines reject illegal terminal rewrites',()=>{
  assert.throws(()=>transitionTask({phase:'OPEN',outcome:'NONE'},{phase:'RUNNING',outcome:'NONE'}));
  assert.throws(()=>transitionActionAttempt({phase:'CLOSED',outcome:'SUCCESS'},{phase:'IN_FLIGHT',outcome:'NONE'}));
  assert.throws(()=>transitionVerification({phase:'RESOLVED',result:'VERIFIED'},{phase:'RUNNING'}));
});

test('context compaction preserves authority-critical state and sanitizes narrative',()=>{
  const manifest=criticalContextManifest({task:{id:'t1',phase:'RUNNING',outcome:'NONE'},taskContract:{contract_id:'c1',contract_version:1,success_criteria:['done']},attempts:[{id:'a1',phase:'RECONCILING',outcome:'NONE',permit_id:'p1'}],blockers:['reconcile a1']});
  assert.equal(validateCompaction(manifest,JSON.parse(JSON.stringify(manifest))).valid,true);
  const view=buildModelContext({manifest,narrative:'token=abcdefghijklmnopqrstuvwxyz0123456789'});
  assert.ok(view.narrative.includes('[REDACTED_SECRET]'));
  const changed={...manifest,blockers:[]};
  assert.equal(validateCompaction(manifest,changed).valid,false);
});
