#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {verifyComputeAttemptReceipt} from '../lib/aqlevon/compute-dispatch.js';
import {
  buildComputeCostReceipt,enforceAuthorizedBudget,estimateBilling,verifyManagerComputeAuthorization,
} from '../lib/aqlevon/compute-cost-orchestrator.js';

function die(message,code=2){console.error(JSON.stringify({event:'p4_cost_finalize_error',error:message}));process.exit(code)}
function readJson(file){try{return JSON.parse(fs.readFileSync(file,'utf8'))}catch{return null}}
function numberArg(value){if(value===undefined||value===null)return null;const n=Number(value);return Number.isFinite(n)&&n>=0?n:null}
function intArg(value){const n=numberArg(value);return Number.isSafeInteger(n)?n:null}
function args(argv){
  const out={attemptReceipt:null,managerAuthorization:null,billingStartEpochMs:null,processEndEpochMs:null,providerHourlyUsd:null,billingGranularitySeconds:1,artifactEgressBytes:0,egressUsdPerGiB:0,examplesProcessed:null,actualBilledWallSeconds:null,actualComputeCostUsd:null,actualEgressCostUsd:null,out:null};
  for(let i=0;i<argv.length;i++){
    const a=argv[i],v=()=>argv[++i];
    if(a==='--attempt-receipt')out.attemptReceipt=v();
    else if(a==='--manager-authorization')out.managerAuthorization=v();
    else if(a==='--billing-start-epoch-ms')out.billingStartEpochMs=intArg(v());
    else if(a==='--process-end-epoch-ms')out.processEndEpochMs=intArg(v());
    else if(a==='--provider-hourly-usd')out.providerHourlyUsd=numberArg(v());
    else if(a==='--billing-granularity-seconds')out.billingGranularitySeconds=intArg(v());
    else if(a==='--artifact-egress-bytes')out.artifactEgressBytes=intArg(v());
    else if(a==='--egress-usd-per-gib')out.egressUsdPerGiB=numberArg(v());
    else if(a==='--examples-processed')out.examplesProcessed=intArg(v());
    else if(a==='--actual-billed-wall-seconds')out.actualBilledWallSeconds=numberArg(v());
    else if(a==='--actual-compute-cost-usd')out.actualComputeCostUsd=numberArg(v());
    else if(a==='--actual-egress-cost-usd')out.actualEgressCostUsd=numberArg(v());
    else if(a==='--out')out.out=v();
    else die(`unknown_arg:${a}`);
  }
  return out;
}

const o=args(process.argv.slice(2));
if(!o.attemptReceipt||!o.out)die('attempt_receipt_and_out_required');
for(const [k,v] of Object.entries({
  billing_start_epoch_ms:o.billingStartEpochMs,process_end_epoch_ms:o.processEndEpochMs,
  provider_hourly_usd:o.providerHourlyUsd,billing_granularity_seconds:o.billingGranularitySeconds,
  artifact_egress_bytes:o.artifactEgressBytes,egress_usd_per_gib:o.egressUsdPerGiB,examples_processed:o.examplesProcessed,
}))if(v===null)die(`invalid_or_missing_${k}`);
const attempt=readJson(o.attemptReceipt);if(!attempt)die('attempt_receipt_json');
const check=verifyComputeAttemptReceipt(attempt);if(!check.ok)die(`attempt_receipt_invalid:${check.reasons.join(',')}`);
const billing=estimateBilling({
  gpuCount:attempt.hardware.gpu_indices.length,providerHourlyUsd:o.providerHourlyUsd,
  billingGranularitySeconds:o.billingGranularitySeconds,billingStartEpochMs:o.billingStartEpochMs,processEndEpochMs:o.processEndEpochMs,
  artifactEgressBytes:o.artifactEgressBytes,egressUsdPerGiB:o.egressUsdPerGiB,
  actualBilledWallSeconds:o.actualBilledWallSeconds,actualComputeCostUsd:o.actualComputeCostUsd,actualEgressCostUsd:o.actualEgressCostUsd,
});
let managerAuthorizationSha256=null;
if(attempt.compute_origin==='paid_manager_authorized'){
  const auth=readJson(o.managerAuthorization);if(!auth)die('manager_authorization_required_for_paid');
  const authCheck=verifyManagerComputeAuthorization(auth);if(!authCheck.ok)die(`manager_authorization_invalid:${authCheck.reasons.join(',')}`);
  if(auth.run_manifest_sha256!==attempt.run_manifest_sha256||auth.profile_id!==attempt.profile_id)die('manager_authorization_attempt_binding_mismatch');
  const budget=enforceAuthorizedBudget({authorization:auth,billing});if(!budget.ok)die(`manager_budget_exceeded:${budget.reasons.join(',')}`,4);
  managerAuthorizationSha256=auth.authorization_sha256;
}
const receipt=buildComputeCostReceipt({
  attemptReceiptSha256:attempt.receipt_sha256,runManifestSha256:attempt.run_manifest_sha256,profileId:attempt.profile_id,
  computeOrigin:attempt.compute_origin,managerAuthorizationSha256,billing,
  gpuCount:attempt.hardware.gpu_indices.length,gpuSeconds:attempt.telemetry.allocated_gpu_seconds,
  peakVramBytes:attempt.telemetry.peak_vram_bytes,tokensProcessed:attempt.telemetry.tokens_processed,
  tokensGenerated:attempt.telemetry.tokens_generated,examplesProcessed:o.examplesProcessed,
  retryIndex:attempt.telemetry.attempt_retry_index,outcome:attempt.outcome.status,
});
fs.mkdirSync(path.dirname(o.out),{recursive:true});
fs.writeFileSync(o.out,JSON.stringify(receipt,null,2)+'\n',{mode:0o600});
console.log(JSON.stringify({event:'p4_cost_receipt_written',receipt_sha256:receipt.receipt_sha256,estimated_total_cost_usd:receipt.billing.estimated_total_cost_usd,actual_total_cost_usd:receipt.billing.actual_total_cost_usd,billed_wall_seconds:receipt.billing.actual_billed_wall_seconds??receipt.billing.observed_billed_wall_seconds,out:o.out}));
