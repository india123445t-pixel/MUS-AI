import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildComputeAttemptReceipt,COMPUTE_PROFILES,validateExecutionAuthorization,verifyComputeAttemptReceipt,
} from '../lib/aqlevon/compute-dispatch.js';
import {
  buildComputeCostReceipt,buildManagerComputeAuthorization,buildVerifiedCandidateCostSummary,
  enforceAuthorizedBudget,estimateBilling,validateP4ExecutionAuthorization,
  verifyComputeCostReceipt,verifyManagerComputeAuthorization,verifyVerifiedCandidateCostSummary,
} from '../lib/aqlevon/compute-cost-orchestrator.js';

const RUN='a'.repeat(64),ATTEMPT='b'.repeat(64),EVAL='c'.repeat(64),ACCEPT='d'.repeat(64),CANDIDATE='e'.repeat(64);
const inventory24=[{index:0,name:'Mock RTX 4090 24GB',memory_mib:24576}];

function paidAuth(overrides={}){
  return buildManagerComputeAuthorization({
    authorizationId:'manager-p4-run-001',
    runTaskId:'P4-A03-GENE1-PHYSICAL-TRAINER',
    runManifestSha256:RUN,
    profileId:'p4-surrogate-1x24',
    maxBilledSeconds:1800,
    maxTotalCostUsd:1,
    maxHourlyRateUsd:1,
    maxArtifactEgressBytes:20_000_000,
    ...overrides,
  });
}
function billing(overrides={}){
  return estimateBilling({
    gpuCount:1,providerHourlyUsd:0.5,billingGranularitySeconds:1,
    billingStartEpochMs:1_000_000,processEndEpochMs:1_060_000,
    artifactEgressBytes:1_000_000,egressUsdPerGiB:0,
    ...overrides,
  });
}

test('P4 profiles prefer one low-cost 24GB surrogate GPU and reserve one 80GB GPU for canonical Gene #1',()=>{
  assert.equal(COMPUTE_PROFILES['p4-surrogate-1x24'].gpu_count,1);
  assert.equal(COMPUTE_PROFILES['p4-surrogate-1x24'].min_vram_mib_each,22000);
  assert.equal(COMPUTE_PROFILES['p4-gene1-27b-1x80'].gpu_count,1);
  assert.equal(COMPUTE_PROFILES['p4-gene1-27b-1x80'].min_vram_mib_each,78000);
});

test('legacy zero-cash authorization still rejects paid origin',()=>{
  const r=validateExecutionAuthorization({authorized:'1',computeOrigin:'paid_manager_authorized'});
  assert.equal(r.ok,false);
  assert.ok(r.reasons.includes('compute_origin_not_zero_cash'));
});

test('manager authorization is self-hashed and bound to exact run task, manifest, profile and caps',()=>{
  const auth=paidAuth();
  const check=verifyManagerComputeAuthorization(auth);
  assert.equal(check.ok,true,check.reasons.join(','));
  assert.equal(auth.compute_origin,'paid_manager_authorized');
  assert.equal(auth.single_use,true);
  assert.match(auth.authorization_sha256,/^[0-9a-f]{64}$/);
  const tampered={...auth,max_billed_seconds:1801};
  assert.equal(verifyManagerComputeAuthorization(tampered).ok,false);
});

test('paid execution requires explicit expected Manager SHA and exact run bindings',()=>{
  const auth=paidAuth();
  const ok=validateP4ExecutionAuthorization({
    authorized:'1',computeOrigin:'paid_manager_authorized',
    runTaskId:'P4-A03-GENE1-PHYSICAL-TRAINER',runManifestSha256:RUN,profileId:'p4-surrogate-1x24',
    providerHourlyUsd:0.5,managerAuthorization:auth,expectedAuthorizationSha256:auth.authorization_sha256,
  });
  assert.equal(ok.ok,true,ok.reasons.join(','));
  for(const changed of [
    {expectedAuthorizationSha256:'f'.repeat(64)},
    {runManifestSha256:'f'.repeat(64)},
    {profileId:'p4-gene1-27b-1x80'},
    {runTaskId:'WRONG-TASK'},
  ]){
    const r=validateP4ExecutionAuthorization({
      authorized:'1',computeOrigin:'paid_manager_authorized',
      runTaskId:'P4-A03-GENE1-PHYSICAL-TRAINER',runManifestSha256:RUN,profileId:'p4-surrogate-1x24',
      providerHourlyUsd:0.5,managerAuthorization:auth,expectedAuthorizationSha256:auth.authorization_sha256,
      ...changed,
    });
    assert.equal(r.ok,false);
  }
});

test('paid authorization rejects provider rate or time*rate plan above Manager cost cap before execution',()=>{
  const auth=paidAuth({maxBilledSeconds:3600,maxTotalCostUsd:0.4,maxHourlyRateUsd:1});
  const r=validateP4ExecutionAuthorization({
    authorized:'1',computeOrigin:'paid_manager_authorized',
    runTaskId:auth.run_task_id,runManifestSha256:RUN,profileId:'p4-surrogate-1x24',
    providerHourlyUsd:0.5,managerAuthorization:auth,expectedAuthorizationSha256:auth.authorization_sha256,
  });
  assert.equal(r.ok,false);
  assert.ok(r.reasons.includes('authorized_time_rate_budget_exceeds_total_cost_cap'));
});

test('billing rounds to provider granularity and accounts artifact egress independently',()=>{
  const b=estimateBilling({
    gpuCount:1,providerHourlyUsd:0.36,billingGranularitySeconds:60,
    billingStartEpochMs:1_000_000,processEndEpochMs:1_061_000,
    artifactEgressBytes:1024**3,egressUsdPerGiB:0.09,
  });
  assert.equal(b.observed_billed_wall_seconds,120);
  assert.equal(b.estimated_compute_cost_usd,'0.012');
  assert.equal(b.estimated_egress_cost_usd,'0.09');
  assert.equal(b.estimated_total_cost_usd,'0.102');
});

test('authorization budget gate checks estimated and provider-actual cost/time/egress',()=>{
  const auth=paidAuth({maxBilledSeconds:120,maxTotalCostUsd:0.2,maxArtifactEgressBytes:2_000_000});
  const good=enforceAuthorizedBudget({authorization:auth,billing:billing()});
  assert.equal(good.ok,true,good.reasons.join(','));
  const bad=enforceAuthorizedBudget({authorization:auth,billing:billing({
    actualBilledWallSeconds:121,actualComputeCostUsd:0.21,actualEgressCostUsd:0,artifactEgressBytes:3_000_000,
  })});
  assert.equal(bad.ok,false);
  assert.ok(bad.reasons.includes('actual_billed_time_exceeds_authorization'));
  assert.ok(bad.reasons.includes('actual_cost_exceeds_authorization'));
  assert.ok(bad.reasons.includes('artifact_egress_exceeds_authorization'));
});

test('P3 compute receipt may represent paid_manager_authorized only after external gate; receipt stays canonical',()=>{
  const r=buildComputeAttemptReceipt({
    attemptId:'attempt-paid',profileId:'p4-surrogate-1x24',runManifestSha256:RUN,
    payloadArgv:['python','train.py'],computeOrigin:'paid_manager_authorized',
    hardware:{inventory:inventory24,gpu_indices:[0]},elapsedMs:1000,
    payloadTelemetry:{schema:'aqlevon-p3-payload-telemetry-v1',peak_vram_bytes:1000,tokens_processed:10,tokens_generated:1},
    retryIndex:0,deviceMemorySamplePeakMib:[1000],sampleIntervalMs:250,status:'success',exitCode:0,
  });
  assert.equal(verifyComputeAttemptReceipt(r).ok,true);
  assert.equal(r.compute_origin,'paid_manager_authorized');
});

test('cost receipt binds paid attempt, Manager authorization and exact work/cost evidence',()=>{
  const auth=paidAuth();
  const r=buildComputeCostReceipt({
    attemptReceiptSha256:ATTEMPT,runManifestSha256:RUN,profileId:'p4-surrogate-1x24',
    computeOrigin:'paid_manager_authorized',managerAuthorizationSha256:auth.authorization_sha256,billing:billing(),
    gpuCount:1,gpuSeconds:'60',peakVramBytes:10_000,tokensProcessed:500,tokensGenerated:50,examplesProcessed:20,
    retryIndex:0,outcome:'success',
  });
  const check=verifyComputeCostReceipt(r);
  assert.equal(check.ok,true,check.reasons.join(','));
  assert.equal(r.work.work_counters_complete,true);
  assert.match(r.receipt_sha256,/^[0-9a-f]{64}$/);
});

test('failed attempt cost remains valid even when work counters are unavailable',()=>{
  const auth=paidAuth();
  const r=buildComputeCostReceipt({
    attemptReceiptSha256:ATTEMPT,runManifestSha256:RUN,profileId:'p4-surrogate-1x24',
    computeOrigin:'paid_manager_authorized',managerAuthorizationSha256:auth.authorization_sha256,billing:billing(),
    gpuCount:1,gpuSeconds:'60',peakVramBytes:null,tokensProcessed:null,tokensGenerated:null,examplesProcessed:null,
    retryIndex:1,outcome:'failed',
  });
  const check=verifyComputeCostReceipt(r);
  assert.equal(check.ok,true,check.reasons.join(','));
  assert.equal(r.work.work_counters_complete,false);
  assert.equal(r.billing.estimated_total_cost_usd,'0.00833333');
});

test('verified-candidate cost summary requires Worker 05 plus Manager acceptance bindings and includes failed spend',()=>{
  const auth=paidAuth();
  const success=buildComputeCostReceipt({
    attemptReceiptSha256:ATTEMPT,runManifestSha256:RUN,profileId:'p4-surrogate-1x24',
    computeOrigin:'paid_manager_authorized',managerAuthorizationSha256:auth.authorization_sha256,billing:billing(),
    gpuCount:1,gpuSeconds:'60',peakVramBytes:1,tokensProcessed:100,tokensGenerated:10,examplesProcessed:5,retryIndex:0,outcome:'success',
  });
  const failed=buildComputeCostReceipt({
    attemptReceiptSha256:'f'.repeat(64),runManifestSha256:RUN,profileId:'p4-surrogate-1x24',
    computeOrigin:'paid_manager_authorized',managerAuthorizationSha256:auth.authorization_sha256,billing:billing({processEndEpochMs:1_030_000}),
    gpuCount:1,gpuSeconds:'30',peakVramBytes:null,tokensProcessed:null,tokensGenerated:null,examplesProcessed:null,retryIndex:1,outcome:'failed',
  });
  const s=buildVerifiedCandidateCostSummary({
    candidateArtifactManifestSha256:CANDIDATE,worker05EvaluationReceiptSha256:EVAL,managerAcceptanceReceiptSha256:ACCEPT,
    costReceipts:[success,failed],
  });
  const check=verifyVerifiedCandidateCostSummary(s);
  assert.equal(check.ok,true,check.reasons.join(','));
  assert.equal(s.attempts,2);
  assert.equal(s.gpu_seconds_total,'90');
  assert.equal(s.work_counter_incomplete_attempts,1);
  assert.equal(s.cost_basis,'estimated_pending_provider_actual');
  assert.ok(Number(s.estimated_total_cost_usd)>Number(success.billing.estimated_total_cost_usd));
});

test('actual provider costs propagate to candidate summary only when complete for every attempt',()=>{
  const auth=paidAuth();
  const make=(sha,cost)=>buildComputeCostReceipt({
    attemptReceiptSha256:sha,runManifestSha256:RUN,profileId:'p4-surrogate-1x24',
    computeOrigin:'paid_manager_authorized',managerAuthorizationSha256:auth.authorization_sha256,
    billing:billing({actualBilledWallSeconds:60,actualComputeCostUsd:cost,actualEgressCostUsd:0}),
    gpuCount:1,gpuSeconds:'60',peakVramBytes:1,tokensProcessed:1,tokensGenerated:0,examplesProcessed:1,retryIndex:0,outcome:'success',
  });
  const s=buildVerifiedCandidateCostSummary({
    candidateArtifactManifestSha256:CANDIDATE,worker05EvaluationReceiptSha256:EVAL,managerAcceptanceReceiptSha256:ACCEPT,
    costReceipts:[make(ATTEMPT,0.01),make('f'.repeat(64),0.02)],
  });
  assert.equal(s.cost_basis,'provider_actual');
  assert.equal(s.actual_total_cost_usd,'0.03');
  assert.equal(verifyVerifiedCandidateCostSummary(s).ok,true);
});
