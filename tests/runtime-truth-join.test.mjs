import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildRequestIdentity,
  buildRuntimeAttemptReceipt,
  EVALUATION_DECISION_RECEIPT_KIND,
  sha256Text,
  validateRuntimeAttemptReceipt,
} from '../lib/aqlevon/runtime-attempt-receipt.js';
import {buildRuntimeAccounting,summarizeVerifiedEfficiency} from '../lib/aqlevon/runtime-economics.js';

const H='1'.repeat(64);
const C='2'.repeat(64);
const E='3'.repeat(64);
const O='4'.repeat(64);
const M='5'.repeat(64);

function receipt({status='success',candidate=C,gpuSeconds=2,cost=0.002,attemptId='attempt-1',taskId='task-1'}={}){
  const metrics=buildRuntimeAccounting({elapsedMs:gpuSeconds*1000,usage:{prompt_tokens:2,completion_tokens:1,total_tokens:3},gpuCount:1,gpuPowerWatts:100,gpuHourlyUsd:cost*3600/gpuSeconds});
  return buildRuntimeAttemptReceipt({
    attemptId,taskId,
    candidateArtifactManifestSha256:candidate,
    requestIdentity:buildRequestIdentity({modelRequest:{model:'AQLEVON-27B',messages:[{role:'user',content:'secret prompt never exported'}]},harnessManifestSha256:H}),
    transportStatus:status,
    failureCode:status==='failure'?'model_http_503':null,
    runtimeMetrics:metrics,
    rawResultSha256:sha256Text(status==='success'?'raw-success':'raw-failure'),
  });
}

test('Runtime Attempt Receipt V1 is deterministic, self-hashed, and exports only request/harness hashes',()=>{
  const a=receipt();
  const b=receipt();
  assert.equal(a.manifest_kind,'AQLEVON_RUNTIME_ATTEMPT_RECEIPT_V1');
  assert.equal(a.receipt_sha256,b.receipt_sha256);
  assert.equal(validateRuntimeAttemptReceipt(a).valid,true);
  const serialized=JSON.stringify(a);
  assert.equal(serialized.includes('secret prompt never exported'),false);
  assert.match(a.request_harness_identity.request_sha256,/^[0-9a-f]{64}$/);
  assert.equal(a.runtime_metric_provenance.estimated_gpu_cost_usd,'estimated:allocated_gpu_seconds_x_configured_gpu_hourly_usd');
});

test('tampering with attempt cost invalidates the self-hash',()=>{
  const a=receipt();
  const tampered={...a,runtime_metrics:{...a.runtime_metrics,estimated_gpu_cost_usd:999}};
  const check=validateRuntimeAttemptReceipt(tampered);
  assert.equal(check.valid,false);
  assert.ok(check.errors.includes('receipt_digest_mismatch'));
});

test('caller verified=true is non-authoritative without an immutable verification receipt join',()=>{
  const a={...receipt(),verified:true};
  const summary=summarizeVerifiedEfficiency([a]);
  assert.equal(summary.status,'INVALID');
  assert.equal(summary.verified_successes,0);

  const clean=receipt();
  const noAuthority=summarizeVerifiedEfficiency([clean]);
  assert.equal(noAuthority.status,'VALID');
  assert.equal(noAuthority.verified_successes,0);
  assert.equal(noAuthority.gpu_seconds_per_verified_success,null);
});

test('Worker-05 evaluation receipt identity verifies only matching successful candidate attempts',()=>{
  const a=receipt();
  const authority={
    receipt_kind:EVALUATION_DECISION_RECEIPT_KIND,
    receipt_sha256:E,
    candidate_artifact_manifest_sha256:C,
    final_status:'PROMOTION_ELIGIBLE',
  };
  const join={attempt_receipt_sha256:a.receipt_sha256,verification_receipt_sha256:E};
  const summary=summarizeVerifiedEfficiency([a],{evaluationDecisionReceipts:[authority],verificationJoins:[join],managerApprovedVerificationReceiptSha256:[E]});
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.verification_sources.evaluation_decision,1);
  assert.equal(summary.gpu_seconds_per_verified_success,a.runtime_metrics.allocated_gpu_seconds);

  const wrongCandidate={...authority,candidate_artifact_manifest_sha256:'9'.repeat(64)};
  const rejected={...authority,final_status:'REJECTED'};
  assert.equal(summarizeVerifiedEfficiency([a],{evaluationDecisionReceipts:[wrongCandidate],verificationJoins:[join],managerApprovedVerificationReceiptSha256:[E]}).verified_successes,0);
  assert.equal(summarizeVerifiedEfficiency([a],{evaluationDecisionReceipts:[rejected],verificationJoins:[join],managerApprovedVerificationReceiptSha256:[E]}).verified_successes,0);
});

test('unapproved verification receipt identities cannot create verified success even when payload looks valid',()=>{
  const a=receipt();
  const authority={receipt_kind:EVALUATION_DECISION_RECEIPT_KIND,receipt_sha256:E,candidate_artifact_manifest_sha256:C,final_status:'PROMOTION_ELIGIBLE'};
  const join={attempt_receipt_sha256:a.receipt_sha256,verification_receipt_sha256:E};
  const summary=summarizeVerifiedEfficiency([a],{evaluationDecisionReceipts:[authority],verificationJoins:[join]});
  assert.equal(summary.status,'VALID');
  assert.equal(summary.verified_successes,0);
  assert.equal(summary.gpu_seconds_per_verified_success,null);
});

test('Manager-approved objective verifier requires exact attempt binding and approval receipt identity',()=>{
  const a=receipt();
  const authority={
    receipt_sha256:O,
    attempt_receipt_sha256:a.receipt_sha256,
    manager_approval_receipt_sha256:M,
    verification_status:'VERIFIED_SUCCESS',
  };
  const join={attempt_receipt_sha256:a.receipt_sha256,verification_receipt_sha256:O};
  const summary=summarizeVerifiedEfficiency([a],{objectiveVerifierApprovals:[authority],verificationJoins:[join],managerApprovedVerificationReceiptSha256:[O]});
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.verification_sources.objective_verifier,1);

  const noApproval={...authority,manager_approval_receipt_sha256:'not-a-hash'};
  assert.equal(summarizeVerifiedEfficiency([a],{objectiveVerifierApprovals:[noApproval],verificationJoins:[join],managerApprovedVerificationReceiptSha256:[O]}).verified_successes,0);
  const wrongAttempt={...authority,attempt_receipt_sha256:'8'.repeat(64)};
  assert.equal(summarizeVerifiedEfficiency([a],{objectiveVerifierApprovals:[wrongAttempt],verificationJoins:[join],managerApprovedVerificationReceiptSha256:[O]}).verified_successes,0);
});

test('failed attempts always retain cost in numerator but can never be verified successes',()=>{
  const success=receipt({attemptId:'a-ok',gpuSeconds:4,cost:0.004});
  const failed=receipt({attemptId:'a-fail',status:'failure',gpuSeconds:2,cost:0.002});
  const evalAuthority={receipt_kind:EVALUATION_DECISION_RECEIPT_KIND,receipt_sha256:E,candidate_artifact_manifest_sha256:C,final_status:'PROMOTION_ELIGIBLE'};
  const joins=[
    {attempt_receipt_sha256:success.receipt_sha256,verification_receipt_sha256:E},
    {attempt_receipt_sha256:failed.receipt_sha256,verification_receipt_sha256:E},
  ];
  const summary=summarizeVerifiedEfficiency([success,failed],{evaluationDecisionReceipts:[evalAuthority],verificationJoins:joins,managerApprovedVerificationReceiptSha256:[E]});
  assert.equal(summary.verified_successes,1);
  assert.equal(summary.allocated_gpu_seconds_total,6);
  assert.equal(summary.gpu_seconds_per_verified_success,6);
  assert.equal(summary.estimated_gpu_cost_usd_total,0.006);
  assert.equal(summary.estimated_gpu_cost_usd_per_verified_success,0.006);
});

test('authoritative aggregation fails closed on any tampered runtime receipt',()=>{
  const a=receipt();
  const bad={...a,task_id:'changed-after-hash'};
  const summary=summarizeVerifiedEfficiency([a,bad]);
  assert.equal(summary.status,'INVALID');
  assert.equal(summary.verified_successes,0);
  assert.equal(summary.allocated_gpu_seconds_total,null);
  assert.equal(summary.invalid_attempt_receipts.length,1);
});
