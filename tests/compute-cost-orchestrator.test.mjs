import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {once} from 'node:events';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {
  buildComputeAttemptReceipt,COMPUTE_PROFILES,validateExecutionAuthorization,verifyComputeAttemptReceipt,
} from '../lib/aqlevon/compute-dispatch.js';
import {
  buildComputeCostReceipt,buildManagerComputeAuthorization,buildVerifiedCandidateCostSummary,
  enforceAuthorizedBudget,estimateBilling,validateP4ExecutionAuthorization,
  verifyComputeCostReceipt,verifyManagerComputeAuthorization,verifyVerifiedCandidateCostSummary,
} from '../lib/aqlevon/compute-cost-orchestrator.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const RUN='a'.repeat(64),P41_RUN='7152cdea6ffd082f632a819e153122b401bd7394ed0273a327537ca961c7fe45',ATTEMPT='b'.repeat(64),EVAL='c'.repeat(64),ACCEPT='d'.repeat(64),CANDIDATE='e'.repeat(64);
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

test('P4.1 exact A1 manifest 7152... binds to the existing surrogate profile without schema or code drift',()=>{
  const auth=paidAuth({authorizationId:'p4-1-template-proof-only',runManifestSha256:P41_RUN});
  const check=verifyManagerComputeAuthorization(auth);
  assert.equal(check.ok,true,check.reasons.join(','));
  const gate=validateP4ExecutionAuthorization({
    authorized:'1',computeOrigin:'paid_manager_authorized',
    runTaskId:'P4-A03-GENE1-PHYSICAL-TRAINER',runManifestSha256:P41_RUN,profileId:'p4-surrogate-1x24',
    providerHourlyUsd:0.34,managerAuthorization:auth,expectedAuthorizationSha256:auth.authorization_sha256,
  });
  assert.equal(gate.ok,true,gate.reasons.join(','));
  assert.equal(auth.run_manifest_sha256,P41_RUN);
  assert.equal(auth.profile_id,'p4-surrogate-1x24');
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


async function runNode(script,args,{env={}}={}){
  const child=spawn(process.execPath,[script,...args],{cwd:root,env:{...process.env,...env},stdio:['ignore','pipe','pipe']});
  let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);
  const [code,signal]=await once(child,'exit');return {code,signal,stdout,stderr};
}

test('paid dispatcher fails before GPU discovery when Manager authorization is absent',async()=>{
  const r=await runNode('scripts/p3-compute-dispatch.mjs',[
    '--profile','p4-surrogate-1x24','--run-task-id','P4-A03-GENE1-PHYSICAL-TRAINER',
    '--run-manifest-sha',RUN,'--provider-hourly-usd','0.5','--gpu-indices','0','--execute','--',
    process.execPath,'-e','process.exit(0)'
  ],{env:{AQLEVON_GPU_EXECUTION_AUTHORIZED:'1',AQLEVON_COMPUTE_ORIGIN:'paid_manager_authorized',AQLEVON_BILLING_START_EPOCH_MS:String(Date.now())}});
  assert.equal(r.code,2);
  assert.ok(r.stderr.includes('manager_authorization'));
});

test('CPU-only fake GPU exercises exact paid gate, strips secret env, and blocks same-workspace replay',async()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'aqlevon-p4-paid-')),bin=path.join(tmp,'bin');
  fs.mkdirSync(bin);const telemetry=path.join(tmp,'telemetry.json'),receipts=path.join(tmp,'receipts'),authFile=path.join(tmp,'auth.json');
  const fake=path.join(bin,'nvidia-smi');
  fs.writeFileSync(fake,`#!/bin/sh
case "$*" in
  *memory.total*) echo '0, Mock RTX 4090 24GB, 24576' ;;
  *memory.used*) echo '0, 1024' ;;
  *) exit 1 ;;
esac
`);fs.chmodSync(fake,0o755);
  const auth=paidAuth({maxBilledSeconds:120,maxTotalCostUsd:1,maxHourlyRateUsd:1});
  fs.writeFileSync(authFile,JSON.stringify(auth));
  const sentinels=['RUNPOD_PROVIDER_SECRET_SENTINEL','HF_SECRET_SENTINEL','LOCAL_SECRET_SENTINEL'];
  const payload=`const fs=require('fs');for(const k of ['RUNPOD_API_KEY','HF_TOKEN','AQLEVON_TEST_SECRET'])if(process.env[k])process.stdout.write(process.env[k]);fs.writeFileSync(process.argv[1],JSON.stringify({schema:'aqlevon-p3-payload-telemetry-v1',peak_vram_bytes:123456,tokens_processed:77,tokens_generated:7}))`;
  const args=[
    '--profile','p4-surrogate-1x24','--run-task-id','P4-A03-GENE1-PHYSICAL-TRAINER',
    '--run-manifest-sha',RUN,'--manager-authorization',authFile,'--provider-hourly-usd','0.5',
    '--gpu-indices','0','--telemetry-json',telemetry,'--receipt-dir',receipts,'--sample-ms','25','--execute','--',
    process.execPath,'-e',payload,telemetry
  ];
  const baseEnv={
    PATH:`${bin}:${process.env.PATH}`,AQLEVON_GPU_EXECUTION_AUTHORIZED:'1',AQLEVON_COMPUTE_ORIGIN:'paid_manager_authorized',
    AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_SHA256:auth.authorization_sha256,
    RUNPOD_API_KEY:sentinels[0],HF_TOKEN:sentinels[1],AQLEVON_TEST_SECRET:sentinels[2],
  };
  const r=await runNode('scripts/p3-compute-dispatch.mjs',args,{env:{...baseEnv,AQLEVON_BILLING_START_EPOCH_MS:String(Date.now())}});
  assert.equal(r.code,0,r.stderr);
  for(const sentinel of sentinels)assert.equal((r.stdout+r.stderr).includes(sentinel),false);
  const files=fs.readdirSync(receipts).filter(x=>x.startsWith('compute-attempt-'));
  assert.equal(files.length,1);
  const attempt=JSON.parse(fs.readFileSync(path.join(receipts,files[0]),'utf8'));
  assert.equal(attempt.compute_origin,'paid_manager_authorized');
  assert.equal(attempt.telemetry.tokens_processed,77);
  assert.equal(verifyComputeAttemptReceipt(attempt).ok,true);
  const replay=await runNode('scripts/p3-compute-dispatch.mjs',args,{env:{...baseEnv,AQLEVON_BILLING_START_EPOCH_MS:String(Date.now())}});
  assert.equal(replay.code,2);
  assert.ok(replay.stderr.includes('manager_authorization_already_used'));
});

test('paid watchdog reserves shutdown margin and SIGKILLs a SIGTERM-resistant payload before authorization expiry',async()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'aqlevon-p4-watchdog-')),bin=path.join(tmp,'bin');
  fs.mkdirSync(bin);const telemetry=path.join(tmp,'telemetry.json'),receipts=path.join(tmp,'receipts'),authFile=path.join(tmp,'auth.json');
  const fake=path.join(bin,'nvidia-smi');
  fs.writeFileSync(fake,`#!/bin/sh
case "$*" in
  *memory.total*) echo '0, Mock RTX 4090 24GB, 24576' ;;
  *memory.used*) echo '0, 1024' ;;
  *) exit 1 ;;
esac
`);fs.chmodSync(fake,0o755);
  const auth=paidAuth({authorizationId:'manager-p4-watchdog-proof',maxBilledSeconds:7,maxTotalCostUsd:1,maxHourlyRateUsd:1});
  fs.writeFileSync(authFile,JSON.stringify(auth));
  const payload=`const fs=require('fs');fs.writeFileSync(process.argv[1],JSON.stringify({schema:'aqlevon-p3-payload-telemetry-v1',peak_vram_bytes:123456,tokens_processed:1,tokens_generated:0}));process.on('SIGTERM',()=>{});setInterval(()=>{},1000)`;
  const started=Date.now();
  const r=await runNode('scripts/p3-compute-dispatch.mjs',[
    '--profile','p4-surrogate-1x24','--run-task-id','P4-A03-GENE1-PHYSICAL-TRAINER','--run-manifest-sha',RUN,
    '--manager-authorization',authFile,'--provider-hourly-usd','0.5','--gpu-indices','0','--telemetry-json',telemetry,
    '--receipt-dir',receipts,'--sample-ms','25','--execute','--',process.execPath,'-e',payload,telemetry
  ],{env:{PATH:`${bin}:${process.env.PATH}`,AQLEVON_GPU_EXECUTION_AUTHORIZED:'1',AQLEVON_COMPUTE_ORIGIN:'paid_manager_authorized',AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_SHA256:auth.authorization_sha256,AQLEVON_BILLING_START_EPOCH_MS:String(Date.now())}});
  const elapsed=Date.now()-started;
  assert.notEqual(r.code,0);
  assert.ok(elapsed<6500,`watchdog elapsed ${elapsed}ms exceeded protected window`);
  const files=fs.readdirSync(receipts).filter(x=>x.startsWith('compute-attempt-'));
  assert.equal(files.length,1);
  const attempt=JSON.parse(fs.readFileSync(path.join(receipts,files[0]),'utf8'));
  assert.equal(attempt.outcome.status,'failed');
  assert.equal(attempt.outcome.failure_code,'manager_budget_timeout');
  assert.ok(Number(attempt.telemetry.allocated_gpu_seconds)>0);
  assert.equal(verifyComputeAttemptReceipt(attempt).ok,true);
});

test('cost finalizer converts a paid attempt into provider-actual cost evidence without rerunning compute',async()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'aqlevon-p4-finalize-')),attemptFile=path.join(tmp,'attempt.json'),authFile=path.join(tmp,'auth.json'),out=path.join(tmp,'cost.json');
  const auth=paidAuth({maxBilledSeconds:120,maxTotalCostUsd:1,maxHourlyRateUsd:1});
  fs.writeFileSync(authFile,JSON.stringify(auth));
  const attempt=buildComputeAttemptReceipt({
    attemptId:'paid-finalize',profileId:'p4-surrogate-1x24',runManifestSha256:RUN,payloadArgv:['python','train.py'],
    computeOrigin:'paid_manager_authorized',hardware:{inventory:inventory24,gpu_indices:[0]},elapsedMs:60_000,
    payloadTelemetry:{schema:'aqlevon-p3-payload-telemetry-v1',peak_vram_bytes:999,tokens_processed:10,tokens_generated:1},
    deviceMemorySamplePeakMib:[1000],sampleIntervalMs:250,status:'success',exitCode:0,
  });
  fs.writeFileSync(attemptFile,JSON.stringify(attempt));
  const r=await runNode('scripts/p4-cost-finalize.mjs',[
    '--attempt-receipt',attemptFile,'--manager-authorization',authFile,
    '--billing-start-epoch-ms','1000000','--process-end-epoch-ms','1060000','--provider-hourly-usd','0.5',
    '--billing-granularity-seconds','1','--artifact-egress-bytes','1000','--egress-usd-per-gib','0',
    '--examples-processed','2','--actual-billed-wall-seconds','60','--actual-compute-cost-usd','0.01',
    '--actual-egress-cost-usd','0','--out',out
  ]);
  assert.equal(r.code,0,r.stderr);
  const cost=JSON.parse(fs.readFileSync(out,'utf8'));
  assert.equal(verifyComputeCostReceipt(cost).ok,true);
  assert.equal(cost.billing.actual_total_cost_usd,'0.01');
  assert.equal(cost.work.examples_processed,2);
});
