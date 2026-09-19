import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CANONICAL_HASH_PROFILE,EVALUATION_DECISION_RECEIPT_KIND,
  buildRequestIdentity,buildRuntimeAttemptReceipt,canonicalDecimalString,canonicalJson,
  hashRuntimeResult,sha256Canonical,validateRuntimeReceiptIdentityConfig,
  verifyP2SelfDigest,verifyRuntimeAttemptReceipt
} from '../lib/aqlevon/runtime-receipts.js';
import {buildRuntimeAccounting,summarizeVerifiedEfficiency} from '../lib/aqlevon/runtime-economics.js';

const CANDIDATE='a'.repeat(64);
const OTHER_CANDIDATE='c'.repeat(64);
const HARNESS='b'.repeat(64);

function metrics(ms=1000,cost=0.01){
  return buildRuntimeAccounting({
    elapsedMs:ms,
    usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15},
    computeDevice:'test-gpu',
    gpuCount:1,
    gpuPowerWatts:300,
    gpuHourlyUsd:cost*3600/(ms/1000)
  });
}

function receipt({attempt='attempt-1',task='task-1',candidate=CANDIDATE,status='success',failure=null,ms=1000,cost=0.01}={}){
  const request={model:'AQLEVON-27B',messages:[{role:'user',content:'private prompt fixture'}],temperature:0.4,stream:false};
  return buildRuntimeAttemptReceipt({
    attemptId:attempt,
    taskId:task,
    candidateArtifactManifestSha256:candidate,
    requestIdentity:buildRequestIdentity({request,harnessManifestSha256:HARNESS}),
    transportOutcome:{status,failure_code:failure},
    runtimeMetrics:metrics(ms,cost),
    rawResultSha256:hashRuntimeResult({choices:[{message:{content:'private response fixture'}}]})
  });
}

function signedReceipt(body){
  const draft={schema_version:1,hash_profile:CANONICAL_HASH_PROFILE,...body};
  return {...draft,receipt_sha256:sha256Canonical(draft)};
}

function evalReceipt({candidate=CANDIDATE,status='PROMOTION_ELIGIBLE'}={}){
  return signedReceipt({
    receipt_kind:EVALUATION_DECISION_RECEIPT_KIND,
    candidate_artifact_manifest_sha256:candidate,
    final_status:status,
  });
}

function objectiveReceipt({id='obj-1',attemptReceipt,candidate=CANDIDATE,verdict='PASS'}={}){
  return signedReceipt({
    receipt_kind:'AQLEVON_OBJECTIVE_VERIFIER_RECEIPT_TEST_V1',
    objective_receipt_id:id,
    attempt_receipt_sha256:attemptReceipt.receipt_sha256,
    candidate_artifact_manifest_sha256:candidate,
    verdict,
  });
}

test('runtime receipt identity config is disabled only when both identities are absent',()=>{
  const none=validateRuntimeReceiptIdentityConfig({});
  assert.equal(none.ok,true);
  assert.equal(none.requested,false);
  assert.equal(none.configured,false);
  const both=validateRuntimeReceiptIdentityConfig({candidateArtifactManifestSha256:CANDIDATE,harnessManifestSha256:HARNESS});
  assert.equal(both.ok,true);
  assert.equal(both.requested,true);
  assert.equal(both.configured,true);
});

test('partial or malformed runtime receipt identity config fails closed deterministically',()=>{
  for(const cfg of [
    {candidateArtifactManifestSha256:CANDIDATE},
    {harnessManifestSha256:HARNESS},
    {candidateArtifactManifestSha256:'not-a-hash',harnessManifestSha256:HARNESS},
    {candidateArtifactManifestSha256:CANDIDATE,harnessManifestSha256:'bad'},
  ]){
    const result=validateRuntimeReceiptIdentityConfig(cfg);
    assert.equal(result.ok,false);
    assert.equal(result.configured,false);
    assert.equal(result.reason,'candidate_and_harness_sha256_required');
  }
});

test('P2.1 canonical JSON uses byte-sorted ASCII keys, NFKC/newline normalization, and decimal strings',()=>{
  const value={'2':'two','10':'ten',text:'e\u0301\r\nline',tiny:1e-7};
  assert.equal(
    canonicalJson(value),
    '{"10":"ten","2":"two","text":"é\\nline","tiny":"0.0000001"}'
  );
  assert.equal(sha256Canonical({tiny:1e-7}),sha256Canonical({tiny:'0.0000001'}));
});

test('canonical decimal strings never use exponent and normalize negative zero',()=>{
  assert.equal(canonicalDecimalString(1e-7),'0.0000001');
  assert.equal(canonicalDecimalString(1.25e6),'1250000');
  assert.equal(canonicalDecimalString(-0),'0');
  assert.equal(canonicalDecimalString(12.3400),'12.34');
});

test('runtime attempt receipt carries canonical hash profile, self-hash, and no prompt/result plaintext',()=>{
  const r=receipt({ms:1250.5,cost:0.01});
  const check=verifyRuntimeAttemptReceipt(r);
  assert.equal(check.ok,true,check.reasons.join(','));
  assert.equal(r.hash_profile,CANONICAL_HASH_PROFILE);
  assert.equal(typeof r.runtime_metrics.elapsed_ms,'string');
  assert.equal(typeof r.runtime_metrics.estimated_gpu_cost_usd,'string');
  const serialized=JSON.stringify(r);
  assert.equal(serialized.includes('private prompt fixture'),false);
  assert.equal(serialized.includes('private response fixture'),false);
  assert.match(r.request_identity.request_sha256,/^[0-9a-f]{64}$/);
  assert.match(r.raw_result_sha256,/^[0-9a-f]{64}$/);
});

test('runtime receipt tampering invalidates the self hash',()=>{
  const r=receipt();
  const tampered={...r,task_id:'other-task'};
  const check=verifyRuntimeAttemptReceipt(tampered);
  assert.equal(check.ok,false);
  assert.ok(check.reasons.includes('receipt_self_hash_mismatch'));
});

test('direct non-integral numbers are forbidden inside an authoritative self-hash payload',()=>{
  const r=receipt();
  const body={...r,runtime_metrics:{...r.runtime_metrics,estimated_gpu_cost_usd:0.01}};
  delete body.receipt_sha256;
  const malformed={...body,receipt_sha256:sha256Canonical(body)};
  assert.equal(verifyP2SelfDigest(malformed),false);
  const check=verifyRuntimeAttemptReceipt(malformed);
  assert.equal(check.ok,false);
  assert.ok(check.reasons.includes('noncanonical_float_representation'));
});

test('missing or unknown hash profile fails closed',()=>{
  const r=receipt();
  const missing={...r};delete missing.hash_profile;
  assert.equal(verifyRuntimeAttemptReceipt(missing).ok,false);
  const unknown={...r,hash_profile:'UNKNOWN_PROFILE'};
  assert.equal(verifyRuntimeAttemptReceipt(unknown).ok,false);
});

test('receipt schema rejects loose verified booleans',()=>{
  const r={...receipt(),verified:true};
  const check=verifyRuntimeAttemptReceipt(r);
  assert.equal(check.ok,false);
  assert.ok(check.reasons.includes('top_level_schema'));
});

test('legacy caller supplied verified=true is non-authoritative',()=>{
  const summary=summarizeVerifiedEfficiency([{verified:true,runtime_metrics:{allocated_gpu_seconds:1}}]);
  assert.equal(summary.status,'INVALID');
  assert.equal(summary.verified_successes,null);
});

test('legacy raw evaluation plus approval-hash truth shape is rejected',()=>{
  const a=receipt(),e=evalReceipt();
  const summary=summarizeVerifiedEfficiency([a],{evaluationReceipts:[e],approvedTruthReceiptSha256s:[e.receipt_sha256]});
  assert.equal(summary.status,'INVALID');
  assert.ok(summary.invalid_reason_codes.includes('truth_authority_schema'));
});

test('candidate-level PROMOTION_ELIGIBLE is accepted as candidate truth but cannot verify an arbitrary attempt',()=>{
  const a=receipt();
  const e=evalReceipt();
  const summary=summarizeVerifiedEfficiency([a],{approvedEvaluationReceipts:[e]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.approved_evaluation_receipts,1);
  assert.equal(summary.verified_successes,0);
  assert.equal(summary.verified_by_evaluation,0);
  assert.equal(summary.gpu_seconds_per_verified_success,null);
});

test('Worker-05 style receipt without P2.1 hash profile is rejected until upstream is P2.1-compliant',()=>{
  const a=receipt();
  const oldStyle={
    schema_version:1,
    receipt_kind:EVALUATION_DECISION_RECEIPT_KIND,
    candidate_artifact_manifest_sha256:CANDIDATE,
    final_status:'PROMOTION_ELIGIBLE',
    receipt_sha256:'d'.repeat(64),
  };
  const summary=summarizeVerifiedEfficiency([a],{approvedEvaluationReceipts:[oldStyle]});
  assert.equal(summary.status,'INVALID');
  assert.ok(summary.invalid_reason_codes.includes('approved_evaluation_receipt_invalid'));
});

test('tampered evaluation receipt cannot reuse an approved self-digest identity',()=>{
  const a=receipt();
  const e=evalReceipt();
  const tampered={...e,final_status:'REJECTED'};
  const summary=summarizeVerifiedEfficiency([a],{approvedEvaluationReceipts:[tampered]});
  assert.equal(summary.status,'INVALID');
  assert.ok(summary.invalid_reason_codes.includes('approved_evaluation_receipt_invalid'));
});

test('Manager-approved per-attempt objective PASS verifies only its exact attempt and candidate',()=>{
  const a1=receipt({attempt:'a1',task:'t1'});
  const a2=receipt({attempt:'a2',task:'t2'});
  const o=objectiveReceipt({attemptReceipt:a1});
  const summary=summarizeVerifiedEfficiency([a1,a2],{approvedObjectiveVerifierReceipts:[o]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.verified_by_objective,1);
  assert.equal(summary.approved_objective_receipts,1);
  assert.equal(summary.gpu_seconds_per_verified_success,2);
});

test('objective PASS bound to the wrong candidate does not verify the attempt',()=>{
  const a=receipt();
  const o=objectiveReceipt({attemptReceipt:a,candidate:OTHER_CANDIDATE});
  const summary=summarizeVerifiedEfficiency([a],{approvedObjectiveVerifierReceipts:[o]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,0);
});

test('conflicting per-attempt objective verdicts fail closed while retaining compute numerator',()=>{
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

test('failed transport never becomes verified even with objective PASS, and its cost stays in numerator',()=>{
  const ok=receipt({attempt:'ok',task:'t-ok',status:'success',ms:1000,cost:0.01});
  const failed=receipt({attempt:'bad',task:'t-bad',status:'failed',failure:'model_http_503',ms:2000,cost:0.02});
  const okVerifier=objectiveReceipt({id:'ok-v',attemptReceipt:ok});
  const failedVerifier=objectiveReceipt({id:'bad-v',attemptReceipt:failed});
  const summary=summarizeVerifiedEfficiency([ok,failed],{approvedObjectiveVerifierReceipts:[okVerifier,failedVerifier]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.transport_successes,1);
  assert.equal(summary.transport_failures,1);
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.allocated_gpu_seconds_total,3);
  assert.equal(summary.gpu_seconds_per_verified_success,3);
  assert.equal(summary.estimated_gpu_cost_usd_per_verified_success,0.03);
});

test('runtime efficiency summary declares operational scope plus attempt-population identity',()=>{
  const a=receipt();
  const o=objectiveReceipt({attemptReceipt:a});
  const summary=summarizeVerifiedEfficiency([a],{approvedObjectiveVerifierReceipts:[o]});
  assert.equal(summary.efficiency_scope_kind,'AQLEVON_RUNTIME_OPERATIONAL_EFFICIENCY_SCOPE_V1');
  assert.equal(summary.population_scope.hash_profile,CANONICAL_HASH_PROFILE);
  assert.equal(summary.population_scope.population_kind,'AQLEVON_RUNTIME_ATTEMPT_POPULATION_V1');
  assert.equal(summary.population_scope.attempt_count,1);
  assert.equal(summary.population_scope.candidate_count,1);
  assert.match(summary.population_scope.attempt_set_sha256,/^[0-9a-f]{64}$/);
});

test('runtime population identity changes when the exact attempt set changes',()=>{
  const a1=receipt({attempt:'a1',task:'t1'});
  const a2=receipt({attempt:'a2',task:'t2'});
  const s1=summarizeVerifiedEfficiency([a1],{});
  const s2=summarizeVerifiedEfficiency([a1,a2],{});
  assert.equal(s1.status,'VALID');
  assert.equal(s2.status,'VALID');
  assert.notEqual(s1.population_scope.attempt_set_sha256,s2.population_scope.attempt_set_sha256);
});
