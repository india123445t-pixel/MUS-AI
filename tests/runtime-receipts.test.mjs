import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CANONICAL_HASH_PROFILE,buildRequestIdentity,buildRuntimeAttemptReceipt,canonicalJson,hashRuntimeResult,sha256Canonical,sha256Text,
  validateRuntimeReceiptIdentityConfig,verifyRuntimeAttemptReceipt
} from '../lib/aqlevon/runtime-receipts.js';
import {buildRuntimeAccounting,summarizeVerifiedEfficiency} from '../lib/aqlevon/runtime-economics.js';

const CANDIDATE='a'.repeat(64);
const HARNESS='b'.repeat(64);
function metrics(ms=1000,cost=0.01){
  return buildRuntimeAccounting({elapsedMs:ms,usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15},computeDevice:'test-gpu',gpuCount:1,gpuPowerWatts:300,gpuHourlyUsd:cost*3600/(ms/1000)});
}
function receipt({attempt='attempt-1',task='task-1',candidate=CANDIDATE,status='success',failure=null,ms=1000,cost=0.01}={}){
  const request={model:'AQLEVON-27B',messages:[{role:'user',content:'private prompt fixture'}],temperature:0,stream:false};
  return buildRuntimeAttemptReceipt({
    attemptId:attempt,taskId:task,candidateArtifactManifestSha256:candidate,
    requestIdentity:buildRequestIdentity({request,harnessManifestSha256:HARNESS}),
    transportOutcome:{status,failure_code:failure},runtimeMetrics:metrics(ms,cost),
    rawResultSha256:hashRuntimeResult({choices:[{message:{content:'private response fixture'}}]})
  });
}
function withReceiptDigest(body){return {...body,receipt_sha256:sha256Canonical(body)}}
function evalReceipt({id='eval-1',candidate=CANDIDATE,status='PROMOTION_ELIGIBLE'}={}){
  void id;
  return withReceiptDigest({schema_version:1,receipt_kind:'AQLEVON_EVALUATION_DECISION_RECEIPT_V1',hash_profile:CANONICAL_HASH_PROFILE,candidate_artifact_manifest_sha256:candidate,final_status:status});
}
function objectiveReceipt({id='obj-1',attemptReceipt,candidate=CANDIDATE,verdict='PASS'}={}){
  return withReceiptDigest({hash_profile:CANONICAL_HASH_PROFILE,objective_receipt_id:id,attempt_receipt_sha256:attemptReceipt.receipt_sha256,candidate_artifact_manifest_sha256:candidate,verdict});
}

test('runtime receipt identity config is disabled only when both identities are absent',()=>{
  const none=validateRuntimeReceiptIdentityConfig({});
  assert.equal(none.ok,true);assert.equal(none.requested,false);assert.equal(none.configured,false);
  const both=validateRuntimeReceiptIdentityConfig({candidateArtifactManifestSha256:CANDIDATE,harnessManifestSha256:HARNESS});
  assert.equal(both.ok,true);assert.equal(both.requested,true);assert.equal(both.configured,true);
});

test('partial or malformed runtime receipt identity config fails closed deterministically',()=>{
  for(const cfg of [
    {candidateArtifactManifestSha256:CANDIDATE},
    {harnessManifestSha256:HARNESS},
    {candidateArtifactManifestSha256:'not-a-hash',harnessManifestSha256:HARNESS},
  ]){
    const result=validateRuntimeReceiptIdentityConfig(cfg);
    assert.equal(result.ok,false);
    assert.equal(result.configured,false);
    assert.equal(result.reason,'candidate_and_harness_sha256_required');
  }
});

test('runtime attempt receipt is self-hashed and exports only hashed request/result identity',()=>{
  const r=receipt();
  const check=verifyRuntimeAttemptReceipt(r);
  assert.equal(check.ok,true,check.reasons.join(','));
  const serialized=JSON.stringify(r);
  assert.equal(serialized.includes('private prompt fixture'),false);
  assert.equal(serialized.includes('private response fixture'),false);
  assert.match(r.request_identity.request_sha256,/^[0-9a-f]{64}$/);
  assert.match(r.raw_result_sha256,/^[0-9a-f]{64}$/);
});

test('receipt tampering invalidates the self hash',()=>{
  const r=receipt();
  const tampered={...r,task_id:'other-task'};
  const check=verifyRuntimeAttemptReceipt(tampered);
  assert.equal(check.ok,false);
  assert.ok(check.reasons.includes('receipt_self_hash_mismatch'));
});

test('receipt schema rejects loose verified booleans or other undeclared truth fields',()=>{
  const r={...receipt(),verified:true};
  const check=verifyRuntimeAttemptReceipt(r);
  assert.equal(check.ok,false);
  assert.ok(check.reasons.includes('top_level_schema'));
});

test('legacy caller supplied verified=true is non-authoritative and makes authoritative summary invalid',()=>{
  const summary=summarizeVerifiedEfficiency([{verified:true,runtime_metrics:{allocated_gpu_seconds:1}}]);
  assert.equal(summary.status,'INVALID');
  assert.equal(summary.verified_successes,null);
});

test('legacy raw receipt plus approval-hash fields are rejected instead of silently acting as authority',()=>{
  const a=receipt(),e=evalReceipt();
  const summary=summarizeVerifiedEfficiency([a],{evaluationReceipts:[e],approvedTruthReceiptSha256s:[e.receipt_sha256]});
  assert.equal(summary.status,'INVALID');
  assert.ok(summary.invalid_reason_codes.includes('truth_authority_schema'));
});

test('candidate-level PROMOTION_ELIGIBLE does not blanket-verify runtime attempts',()=>{
  const a=receipt({ms:1000,cost:0.01});
  const e=evalReceipt();
  const summary=summarizeVerifiedEfficiency([a],{approvedEvaluationReceipts:[e]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,0);
  assert.equal(summary.verified_by_evaluation,0);
  assert.equal(summary.verified_by_objective,0);
  assert.equal(summary.approved_evaluation_receipts,1);
  assert.equal(summary.gpu_seconds_per_verified_success,null);
});

test('approved evaluation for a different candidate does not verify the attempt',()=>{
  const a=receipt();
  const e=evalReceipt({candidate:'c'.repeat(64)});
  const summary=summarizeVerifiedEfficiency([a],{approvedEvaluationReceipts:[e]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,0);
});

test('approved REJECTED evaluation does not count as verified success',()=>{
  const a=receipt();
  const e=evalReceipt({status:'REJECTED'});
  const summary=summarizeVerifiedEfficiency([a],{approvedEvaluationReceipts:[e]});
  assert.equal(summary.verified_successes,0);
});

test('tampered evaluation projection cannot reuse an approved self-digest identity',()=>{
  const a=receipt();
  const first=evalReceipt({status:'PROMOTION_ELIGIBLE'});
  const tampered={...first,final_status:'REJECTED'};
  const summary=summarizeVerifiedEfficiency([a],{approvedEvaluationReceipts:[first,tampered]});
  assert.equal(summary.status,'INVALID');
  assert.ok(summary.invalid_reason_codes.includes('approved_evaluation_receipt_invalid'));
});

test('Manager-approved per-attempt objective PASS verifies only its linked attempt',()=>{
  const a1=receipt({attempt:'a1',task:'t1'});
  const a2=receipt({attempt:'a2',task:'t2'});
  const o=objectiveReceipt({attemptReceipt:a1});
  const summary=summarizeVerifiedEfficiency([a1,a2],{approvedObjectiveVerifierReceipts:[o]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.verified_by_objective,1);
  assert.equal(summary.approved_objective_receipts,1);
});

test('conflicting approved objective receipts fail closed for verification while retaining cost',()=>{
  const a=receipt({ms:2000,cost:0.02});
  const pass=objectiveReceipt({id:'obj-pass',attemptReceipt:a,verdict:'PASS'});
  const fail=objectiveReceipt({id:'obj-fail',attemptReceipt:a,verdict:'FAIL'});
  const summary=summarizeVerifiedEfficiency([a],{approvedObjectiveVerifierReceipts:[pass,fail]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,0);
  assert.equal(summary.truth_conflicts,1);
  assert.equal(summary.allocated_gpu_seconds_total,2);
  assert.equal(summary.gpu_seconds_per_verified_success,null);
});

test('failed transport never becomes verified and still charges numerator cost',()=>{
  const ok=receipt({attempt:'ok',task:'t-ok',status:'success',ms:1000,cost:0.01});
  const failed=receipt({attempt:'bad',task:'t-bad',status:'failed',failure:'model_http_503',ms:2000,cost:0.02});
  const objective=objectiveReceipt({attemptReceipt:ok});
  const summary=summarizeVerifiedEfficiency([ok,failed],{approvedObjectiveVerifierReceipts:[objective]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.transport_successes,1);
  assert.equal(summary.transport_failures,1);
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.allocated_gpu_seconds_total,3);
  assert.equal(summary.gpu_seconds_per_verified_success,3);
  assert.equal(summary.estimated_gpu_cost_usd_per_verified_success,0.03);
});

test('malformed Manager-approved evaluation receipt invalidates the authoritative truth join',()=>{
  const a=receipt();
  const bad=withReceiptDigest({schema_version:1,receipt_kind:'AQLEVON_EVALUATION_DECISION_RECEIPT_V1',hash_profile:CANONICAL_HASH_PROFILE,candidate_artifact_manifest_sha256:'not-a-hash',final_status:'PROMOTION_ELIGIBLE'});
  const summary=summarizeVerifiedEfficiency([a],{approvedEvaluationReceipts:[bad]});
  assert.equal(summary.status,'INVALID');
  assert.ok(summary.invalid_reason_codes.includes('approved_evaluation_receipt_invalid'));
});


test('P2.1 canonical hash profile normalizes Unicode/newlines and non-integral numbers without exponent',()=>{
  assert.equal(canonicalJson({text:'e\u0301\r\nline',tiny:1e-7}),'{"text":"é\\nline","tiny":"0.0000001"}');
  assert.equal(sha256Canonical({tiny:1e-7}),sha256Canonical({tiny:'0.0000001'}));
});

test('runtime receipt carries canonical hash profile and canonical decimal metrics',()=>{
  const r=receipt({ms:1250,cost:0.01});
  assert.equal(r.hash_profile,CANONICAL_HASH_PROFILE);
  assert.equal(typeof r.runtime_metrics.elapsed_ms,'number');
  assert.equal(typeof r.runtime_metrics.estimated_gpu_cost_usd,'string');
  assert.equal(verifyRuntimeAttemptReceipt(r).ok,true);
});

test('missing or unknown hash profile makes runtime and approved truth receipts fail closed',()=>{
  const r=receipt();
  const missing={...r}; delete missing.hash_profile;
  assert.equal(verifyRuntimeAttemptReceipt(missing).ok,false);
  const e=evalReceipt();
  const bad={...e,hash_profile:'UNKNOWN_PROFILE'};
  const summary=summarizeVerifiedEfficiency([r],{approvedEvaluationReceipts:[bad]});
  assert.equal(summary.status,'INVALID');
  assert.ok(summary.invalid_reason_codes.includes('approved_evaluation_receipt_invalid'));
});

test('tampered Manager-approved objective receipt is rejected by shared canonical self-digest',()=>{
  const a=receipt();
  const o=objectiveReceipt({attemptReceipt:a});
  const tampered={...o,verdict:'FAIL'};
  const summary=summarizeVerifiedEfficiency([a],{approvedObjectiveVerifierReceipts:[tampered]});
  assert.equal(summary.status,'INVALID');
  assert.ok(summary.invalid_reason_codes.includes('approved_objective_receipt_invalid'));
});

test('runtime efficiency summary declares a bound operational population identity',()=>{
  const a=receipt();
  const o=objectiveReceipt({attemptReceipt:a});
  const summary=summarizeVerifiedEfficiency([a],{approvedObjectiveVerifierReceipts:[o]});
  assert.equal(summary.population_scope.scope_kind,'AQLEVON_RUNTIME_OPERATIONAL_EFFICIENCY_SCOPE_V1');
  assert.equal(summary.population_scope.hash_profile,CANONICAL_HASH_PROFILE);
  assert.equal(summary.population_scope.identity_status,'BOUND');
  assert.match(summary.population_scope.population_identity_sha256,/^[0-9a-f]{64}$/);
  assert.deepEqual(summary.population_scope.attempt_receipt_sha256s,[a.receipt_sha256]);
});
