import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildRequestIdentity,buildRuntimeAttemptReceipt,hashRuntimeResult,sha256Text,verifyRuntimeAttemptReceipt
} from '../lib/aqlevon/runtime-receipts.js';
import {buildRuntimeAccounting,summarizeVerifiedEfficiency} from '../lib/aqlevon/runtime-economics.js';

const CANDIDATE='a'.repeat(64);
const HARNESS='b'.repeat(64);
function metrics(ms=1000,cost=0.01){
  return buildRuntimeAccounting({elapsedMs:ms,usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15},computeDevice:'test-gpu',gpuCount:1,gpuPowerWatts:300,gpuHourlyUsd:cost*3600/(ms/1000)});
}
function receipt({attempt='attempt-1',task='task-1',candidate=CANDIDATE,status='success',failure=null,ms=1000,cost=0.01}={}){
  const request={model:'AQLEVON-27B',messages:[{role:'user',content:'secret prompt text'}],temperature:0,stream:false};
  return buildRuntimeAttemptReceipt({
    attemptId:attempt,taskId:task,candidateArtifactManifestSha256:candidate,
    requestIdentity:buildRequestIdentity({request,harnessManifestSha256:HARNESS}),
    transportOutcome:{status,failure_code:failure},runtimeMetrics:metrics(ms,cost),
    rawResultSha256:hashRuntimeResult({choices:[{message:{content:'secret response text'}}]})
  });
}
function evalReceipt({id='eval-1',candidate=CANDIDATE,status='PROMOTION_ELIGIBLE'}={}){
  return {receipt_kind:'AQLEVON_EVALUATION_DECISION_RECEIPT_V1',receipt_sha256:sha256Text(id),candidate_artifact_manifest_sha256:candidate,final_status:status};
}
function objectiveReceipt({id='obj-1',attemptReceipt,candidate=CANDIDATE,verdict='PASS'}={}){
  return {receipt_sha256:sha256Text(id),attempt_receipt_sha256:attemptReceipt.receipt_sha256,candidate_artifact_manifest_sha256:candidate,verdict};
}

test('runtime attempt receipt is self-hashed and exports only hashed request/result identity',()=>{
  const r=receipt();
  const check=verifyRuntimeAttemptReceipt(r);
  assert.equal(check.ok,true,check.reasons.join(','));
  const serialized=JSON.stringify(r);
  assert.equal(serialized.includes('secret prompt text'),false);
  assert.equal(serialized.includes('secret response text'),false);
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

test('unapproved evaluation receipt cannot create a verified success',()=>{
  const a=receipt();
  const e=evalReceipt();
  const summary=summarizeVerifiedEfficiency([a],{evaluationReceipts:[e],approvedTruthReceiptSha256s:[]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,0);
  assert.equal(summary.unapproved_truth_receipts_ignored,1);
  assert.equal(summary.gpu_seconds_per_verified_success,null);
});

test('Manager-approved promotion evaluation can verify successful attempt for matching candidate',()=>{
  const a=receipt({ms:1000,cost:0.01});
  const e=evalReceipt();
  const summary=summarizeVerifiedEfficiency([a],{evaluationReceipts:[e],approvedTruthReceiptSha256s:[e.receipt_sha256]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.verified_by_evaluation,1);
  assert.equal(summary.verified_by_objective,0);
  assert.equal(summary.gpu_seconds_per_verified_success,1);
});

test('approved evaluation for a different candidate does not verify the attempt',()=>{
  const a=receipt();
  const e=evalReceipt({candidate:'c'.repeat(64)});
  const summary=summarizeVerifiedEfficiency([a],{evaluationReceipts:[e],approvedTruthReceiptSha256s:[e.receipt_sha256]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,0);
});

test('approved REJECTED evaluation does not count as verified success',()=>{
  const a=receipt();
  const e=evalReceipt({status:'REJECTED'});
  const summary=summarizeVerifiedEfficiency([a],{evaluationReceipts:[e],approvedTruthReceiptSha256s:[e.receipt_sha256]});
  assert.equal(summary.verified_successes,0);
});

test('Manager-approved per-attempt objective PASS verifies only its linked attempt',()=>{
  const a1=receipt({attempt:'a1',task:'t1'});
  const a2=receipt({attempt:'a2',task:'t2'});
  const o=objectiveReceipt({attemptReceipt:a1});
  const summary=summarizeVerifiedEfficiency([a1,a2],{objectiveVerifierReceipts:[o],approvedTruthReceiptSha256s:[o.receipt_sha256]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.verified_by_objective,1);
});

test('conflicting approved objective receipts fail closed for verification while retaining cost',()=>{
  const a=receipt({ms:2000,cost:0.02});
  const pass=objectiveReceipt({id:'obj-pass',attemptReceipt:a,verdict:'PASS'});
  const fail=objectiveReceipt({id:'obj-fail',attemptReceipt:a,verdict:'FAIL'});
  const summary=summarizeVerifiedEfficiency([a],{objectiveVerifierReceipts:[pass,fail],approvedTruthReceiptSha256s:[pass.receipt_sha256,fail.receipt_sha256]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,0);
  assert.equal(summary.truth_conflicts,1);
  assert.equal(summary.allocated_gpu_seconds_total,2);
  assert.equal(summary.gpu_seconds_per_verified_success,null);
});

test('failed transport never becomes verified and still charges numerator cost',()=>{
  const ok=receipt({attempt:'ok',task:'t-ok',status:'success',ms:1000,cost:0.01});
  const failed=receipt({attempt:'bad',task:'t-bad',status:'failed',failure:'model_http_503',ms:2000,cost:0.02});
  const e=evalReceipt();
  const summary=summarizeVerifiedEfficiency([ok,failed],{evaluationReceipts:[e],approvedTruthReceiptSha256s:[e.receipt_sha256]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.transport_successes,1);
  assert.equal(summary.transport_failures,1);
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.allocated_gpu_seconds_total,3);
  assert.equal(summary.gpu_seconds_per_verified_success,3);
  assert.equal(summary.estimated_gpu_cost_usd_per_verified_success,0.03);
});

test('malformed receipt whose identity is Manager-approved invalidates the authoritative truth join',()=>{
  const a=receipt();
  const bad={receipt_kind:'AQLEVON_EVALUATION_DECISION_RECEIPT_V1',receipt_sha256:sha256Text('approved-bad'),candidate_artifact_manifest_sha256:'not-a-hash',final_status:'PROMOTION_ELIGIBLE'};
  const summary=summarizeVerifiedEfficiency([a],{evaluationReceipts:[bad],approvedTruthReceiptSha256s:[bad.receipt_sha256]});
  assert.equal(summary.status,'INVALID');
  assert.ok(summary.invalid_reason_codes.includes('approved_evaluation_receipt_invalid'));
});
