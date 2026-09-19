import {
  P2_HASH_PROFILE,
  canonicalDecimalString,
  isSha256Hex,
  sha256Canonical,
  verifyP2SelfDigest,
} from './runtime-receipts.js';
import {getComputeProfile} from './compute-dispatch.js';

export const P4_COMPUTE_TASK_ID='P4-A06-COMPUTE-COST-ORCHESTRATOR';
export const MANAGER_COMPUTE_AUTHORIZATION_KIND='AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_V1';
export const COMPUTE_COST_RECEIPT_KIND='AQLEVON_COMPUTE_COST_RECEIPT_V1';
export const VERIFIED_CANDIDATE_COST_KIND='AQLEVON_VERIFIED_CANDIDATE_COST_SUMMARY_V1';

const PAID_ORIGIN='paid_manager_authorized';
const ZERO_CASH_ORIGINS=new Set(['owned','donated','free']);
const AUTH_KEYS=new Set([
  'schema_version','authorization_kind','hash_profile','authorization_id','run_task_id','run_manifest_sha256',
  'profile_id','compute_origin','max_billed_seconds','max_total_cost_usd','max_hourly_rate_usd',
  'max_artifact_egress_bytes','single_use','authorization_sha256',
]);
const COST_KEYS=new Set([
  'schema_version','receipt_kind','hash_profile','task_id','attempt_receipt_sha256','run_manifest_sha256',
  'profile_id','compute_origin','manager_authorization_sha256','billing','work','receipt_sha256',
]);
const BILLING_KEYS=new Set([
  'provider_rate_usd_per_gpu_hour','billing_granularity_seconds','billing_start_epoch_ms','process_end_epoch_ms',
  'observed_billed_wall_seconds','estimated_compute_cost_usd','artifact_egress_bytes','egress_rate_usd_per_gib',
  'estimated_egress_cost_usd','estimated_total_cost_usd','actual_billed_wall_seconds','actual_compute_cost_usd',
  'actual_egress_cost_usd','actual_total_cost_usd',
]);
const WORK_KEYS=new Set(['gpu_count','gpu_seconds','work_counters_complete','peak_vram_bytes','tokens_processed','tokens_generated','examples_processed','retry_index','outcome']);
const SUMMARY_KEYS=new Set([
  'schema_version','summary_kind','hash_profile','candidate_artifact_manifest_sha256',
  'worker05_evaluation_receipt_sha256','manager_acceptance_receipt_sha256','attempt_cost_receipt_sha256s',
  'attempts','gpu_seconds_total','billed_wall_seconds_total','tokens_processed_total','examples_processed_total','work_counter_incomplete_attempts',
  'artifact_egress_bytes_total','estimated_total_cost_usd','actual_total_cost_usd','cost_basis','summary_sha256',
]);
const SHA_RE=/^[0-9a-f]{64}$/;

function exactKeys(value,allowed){
  if(!value||typeof value!=='object'||Array.isArray(value))return false;
  const keys=Object.keys(value);
  return keys.length===allowed.size&&keys.every(key=>allowed.has(key));
}
function id(value){return typeof value==='string'&&value.length>0&&value.length<=256}
function integer(value,{min=0,max=Number.MAX_SAFE_INTEGER}={}){
  return Number.isSafeInteger(value)&&value>=min&&value<=max;
}
function nonNegativeNumber(value){
  const n=Number(value);
  return Number.isFinite(n)&&n>=0?n:null;
}
function money(value){
  const n=nonNegativeNumber(value);
  if(n===null)throw new TypeError('invalid_nonnegative_decimal');
  const rounded=Math.round((n+Number.EPSILON)*1e8)/1e8;
  return canonicalDecimalString(rounded);
}
function optionalMoney(value){return value===null||value===undefined?null:money(value)}
function canonicalSeconds(value){
  const n=nonNegativeNumber(value);
  if(n===null)throw new TypeError('invalid_seconds');
  return canonicalDecimalString(n);
}
function isCanonicalDecimal(value){
  if(typeof value!=='string')return false;
  const n=Number(value);
  if(!Number.isFinite(n)||n<0)return false;
  return canonicalDecimalString(n)===value;
}

export function buildManagerComputeAuthorization({
  authorizationId,runTaskId,runManifestSha256,profileId,maxBilledSeconds,maxTotalCostUsd,
  maxHourlyRateUsd,maxArtifactEgressBytes=0,
}={}){
  if(!id(authorizationId))throw new TypeError('authorization_id');
  if(!id(runTaskId))throw new TypeError('run_task_id');
  if(!isSha256Hex(runManifestSha256))throw new TypeError('run_manifest_sha256');
  if(!getComputeProfile(profileId))throw new TypeError('profile_id');
  if(!integer(maxBilledSeconds,{min:1,max:604800}))throw new TypeError('max_billed_seconds');
  if(!integer(maxArtifactEgressBytes,{min:0}))throw new TypeError('max_artifact_egress_bytes');
  const draft={
    schema_version:1,
    authorization_kind:MANAGER_COMPUTE_AUTHORIZATION_KIND,
    hash_profile:P2_HASH_PROFILE,
    authorization_id:String(authorizationId),
    run_task_id:String(runTaskId),
    run_manifest_sha256:String(runManifestSha256),
    profile_id:String(profileId),
    compute_origin:PAID_ORIGIN,
    max_billed_seconds:maxBilledSeconds,
    max_total_cost_usd:money(maxTotalCostUsd),
    max_hourly_rate_usd:money(maxHourlyRateUsd),
    max_artifact_egress_bytes:maxArtifactEgressBytes,
    single_use:true,
  };
  return Object.freeze({...draft,authorization_sha256:sha256Canonical(draft)});
}

export function verifyManagerComputeAuthorization(auth){
  const reasons=[];
  if(!exactKeys(auth,AUTH_KEYS))reasons.push('authorization_schema');
  if(auth?.schema_version!==1)reasons.push('schema_version');
  if(auth?.authorization_kind!==MANAGER_COMPUTE_AUTHORIZATION_KIND)reasons.push('authorization_kind');
  if(auth?.hash_profile!==P2_HASH_PROFILE)reasons.push('hash_profile');
  if(!id(auth?.authorization_id))reasons.push('authorization_id');
  if(!id(auth?.run_task_id))reasons.push('run_task_id');
  if(!SHA_RE.test(auth?.run_manifest_sha256||''))reasons.push('run_manifest_sha256');
  if(!getComputeProfile(auth?.profile_id))reasons.push('profile_id');
  if(auth?.compute_origin!==PAID_ORIGIN)reasons.push('compute_origin');
  if(!integer(auth?.max_billed_seconds,{min:1,max:604800}))reasons.push('max_billed_seconds');
  if(!isCanonicalDecimal(auth?.max_total_cost_usd))reasons.push('max_total_cost_usd');
  if(!isCanonicalDecimal(auth?.max_hourly_rate_usd))reasons.push('max_hourly_rate_usd');
  if(!integer(auth?.max_artifact_egress_bytes,{min:0}))reasons.push('max_artifact_egress_bytes');
  if(auth?.single_use!==true)reasons.push('single_use');
  if(!SHA_RE.test(auth?.authorization_sha256||''))reasons.push('authorization_sha256');
  if(reasons.length===0&&!verifyP2SelfDigest(auth,{digestField:'authorization_sha256'}))reasons.push('authorization_self_hash_mismatch');
  return Object.freeze({ok:reasons.length===0,reasons:Object.freeze(reasons)});
}

export function validateP4ExecutionAuthorization({
  authorized,computeOrigin,runTaskId,runManifestSha256,profileId,providerHourlyUsd,
  managerAuthorization=null,expectedAuthorizationSha256=null,
}={}){
  const origin=String(computeOrigin||'').trim().toLowerCase();
  const reasons=[];
  if(String(authorized)!=='1')reasons.push('gpu_execution_not_authorized');
  if(ZERO_CASH_ORIGINS.has(origin)){
    return Object.freeze({ok:reasons.length===0,compute_origin:origin,manager_authorization_sha256:null,max_billed_seconds:null,max_total_cost_usd:null,reasons:Object.freeze(reasons)});
  }
  if(origin!==PAID_ORIGIN){
    reasons.push('compute_origin_not_authorized');
    return Object.freeze({ok:false,compute_origin:null,manager_authorization_sha256:null,max_billed_seconds:null,max_total_cost_usd:null,reasons:Object.freeze(reasons)});
  }
  const check=verifyManagerComputeAuthorization(managerAuthorization);
  if(!check.ok)reasons.push(...check.reasons.map(x=>`manager_${x}`));
  if(!SHA_RE.test(String(expectedAuthorizationSha256||'')))reasons.push('manager_authorization_expected_sha256_required');
  if(check.ok&&managerAuthorization.authorization_sha256!==expectedAuthorizationSha256)reasons.push('manager_authorization_sha256_mismatch');
  if(check.ok&&managerAuthorization.run_task_id!==String(runTaskId||''))reasons.push('manager_run_task_mismatch');
  if(check.ok&&managerAuthorization.run_manifest_sha256!==String(runManifestSha256||''))reasons.push('manager_run_manifest_mismatch');
  if(check.ok&&managerAuthorization.profile_id!==String(profileId||''))reasons.push('manager_profile_mismatch');
  const rate=nonNegativeNumber(providerHourlyUsd);
  if(rate===null)reasons.push('provider_hourly_rate_required');
  else if(check.ok){
    if(rate>Number(managerAuthorization.max_hourly_rate_usd))reasons.push('provider_hourly_rate_exceeds_authorization');
    const profile=getComputeProfile(profileId);
    const projectedComputeCost=managerAuthorization.max_billed_seconds*profile.gpu_count*rate/3600;
    if(projectedComputeCost>Number(managerAuthorization.max_total_cost_usd))reasons.push('authorized_time_rate_budget_exceeds_total_cost_cap');
  }
  return Object.freeze({
    ok:reasons.length===0,
    compute_origin:reasons.length===0?PAID_ORIGIN:null,
    manager_authorization_sha256:check.ok?managerAuthorization.authorization_sha256:null,
    max_billed_seconds:check.ok?managerAuthorization.max_billed_seconds:null,
    max_total_cost_usd:check.ok?managerAuthorization.max_total_cost_usd:null,
    max_artifact_egress_bytes:check.ok?managerAuthorization.max_artifact_egress_bytes:null,
    reasons:Object.freeze(reasons),
  });
}

export function estimateBilling({
  gpuCount,providerHourlyUsd,billingGranularitySeconds=1,billingStartEpochMs,processEndEpochMs,
  artifactEgressBytes=0,egressUsdPerGiB=0,actualBilledWallSeconds=null,actualComputeCostUsd=null,actualEgressCostUsd=null,
}={}){
  if(!integer(gpuCount,{min:1,max:64}))throw new TypeError('gpu_count');
  if(!integer(billingGranularitySeconds,{min:1,max:3600}))throw new TypeError('billing_granularity_seconds');
  if(!integer(billingStartEpochMs,{min:0})||!integer(processEndEpochMs,{min:billingStartEpochMs}))throw new TypeError('billing_epoch_ms');
  if(!integer(artifactEgressBytes,{min:0}))throw new TypeError('artifact_egress_bytes');
  const hourly=nonNegativeNumber(providerHourlyUsd),egressRate=nonNegativeNumber(egressUsdPerGiB);
  if(hourly===null)throw new TypeError('provider_hourly_usd');
  if(egressRate===null)throw new TypeError('egress_usd_per_gib');
  const rawSeconds=(processEndEpochMs-billingStartEpochMs)/1000;
  const billedSeconds=Math.ceil(rawSeconds/billingGranularitySeconds)*billingGranularitySeconds;
  const computeCost=billedSeconds*gpuCount*hourly/3600;
  const egressCost=artifactEgressBytes/(1024**3)*egressRate;
  const actualSeconds=actualBilledWallSeconds===null?null:nonNegativeNumber(actualBilledWallSeconds);
  if(actualBilledWallSeconds!==null&&actualSeconds===null)throw new TypeError('actual_billed_wall_seconds');
  const actualCompute=actualComputeCostUsd===null?null:nonNegativeNumber(actualComputeCostUsd);
  const actualEgress=actualEgressCostUsd===null?null:nonNegativeNumber(actualEgressCostUsd);
  if(actualComputeCostUsd!==null&&actualCompute===null)throw new TypeError('actual_compute_cost_usd');
  if(actualEgressCostUsd!==null&&actualEgress===null)throw new TypeError('actual_egress_cost_usd');
  const actualTotal=actualCompute!==null&&actualEgress!==null?actualCompute+actualEgress:null;
  return Object.freeze({
    provider_rate_usd_per_gpu_hour:money(hourly),
    billing_granularity_seconds:billingGranularitySeconds,
    billing_start_epoch_ms:billingStartEpochMs,
    process_end_epoch_ms:processEndEpochMs,
    observed_billed_wall_seconds:billedSeconds,
    estimated_compute_cost_usd:money(computeCost),
    artifact_egress_bytes:artifactEgressBytes,
    egress_rate_usd_per_gib:money(egressRate),
    estimated_egress_cost_usd:money(egressCost),
    estimated_total_cost_usd:money(computeCost+egressCost),
    actual_billed_wall_seconds:actualSeconds===null?null:canonicalSeconds(actualSeconds),
    actual_compute_cost_usd:actualCompute===null?null:money(actualCompute),
    actual_egress_cost_usd:actualEgress===null?null:money(actualEgress),
    actual_total_cost_usd:actualTotal===null?null:money(actualTotal),
  });
}

export function buildComputeCostReceipt({
  attemptReceiptSha256,runManifestSha256,profileId,computeOrigin,managerAuthorizationSha256=null,billing,
  gpuCount,gpuSeconds,peakVramBytes,tokensProcessed,tokensGenerated=0,examplesProcessed,retryIndex,outcome,
}={}){
  if(!isSha256Hex(attemptReceiptSha256))throw new TypeError('attempt_receipt_sha256');
  if(!isSha256Hex(runManifestSha256))throw new TypeError('run_manifest_sha256');
  if(!getComputeProfile(profileId))throw new TypeError('profile_id');
  if(!ZERO_CASH_ORIGINS.has(computeOrigin)&&computeOrigin!==PAID_ORIGIN)throw new TypeError('compute_origin');
  if(computeOrigin===PAID_ORIGIN&&!isSha256Hex(managerAuthorizationSha256))throw new TypeError('manager_authorization_sha256');
  if(computeOrigin!==PAID_ORIGIN&&managerAuthorizationSha256!==null)throw new TypeError('unexpected_manager_authorization_sha256');
  if(!billing||!exactKeys(billing,BILLING_KEYS))throw new TypeError('billing_schema');
  if(!integer(gpuCount,{min:1,max:64}))throw new TypeError('gpu_count');
  if(!isCanonicalDecimal(String(gpuSeconds)))throw new TypeError('gpu_seconds');
  const counters=[peakVramBytes,tokensProcessed,tokensGenerated,examplesProcessed];
  const countersComplete=counters.every(v=>v!==null&&v!==undefined);
  if(counters.some(v=>v!==null&&v!==undefined&&!integer(v,{min:0})))throw new TypeError('work_counters');
  if(peakVramBytes!==null&&peakVramBytes!==undefined&&!integer(peakVramBytes,{min:1}))throw new TypeError('peak_vram_bytes');
  if(!integer(retryIndex,{min:0,max:3}))throw new TypeError('retry_index');
  if(!['success','failed'].includes(outcome))throw new TypeError('outcome');
  const draft={
    schema_version:1,
    receipt_kind:COMPUTE_COST_RECEIPT_KIND,
    hash_profile:P2_HASH_PROFILE,
    task_id:P4_COMPUTE_TASK_ID,
    attempt_receipt_sha256:attemptReceiptSha256,
    run_manifest_sha256:runManifestSha256,
    profile_id:String(profileId),
    compute_origin:String(computeOrigin),
    manager_authorization_sha256:managerAuthorizationSha256,
    billing,
    work:{
      gpu_count:gpuCount,
      gpu_seconds:String(gpuSeconds),
      work_counters_complete:countersComplete,
      peak_vram_bytes:peakVramBytes??null,
      tokens_processed:tokensProcessed??null,
      tokens_generated:tokensGenerated??null,
      examples_processed:examplesProcessed??null,
      retry_index:retryIndex,
      outcome,
    },
  };
  return Object.freeze({...draft,receipt_sha256:sha256Canonical(draft)});
}

export function verifyComputeCostReceipt(receipt){
  const reasons=[];
  if(!exactKeys(receipt,COST_KEYS))reasons.push('cost_schema');
  if(receipt?.schema_version!==1)reasons.push('schema_version');
  if(receipt?.receipt_kind!==COMPUTE_COST_RECEIPT_KIND)reasons.push('receipt_kind');
  if(receipt?.hash_profile!==P2_HASH_PROFILE)reasons.push('hash_profile');
  if(receipt?.task_id!==P4_COMPUTE_TASK_ID)reasons.push('task_id');
  if(!SHA_RE.test(receipt?.attempt_receipt_sha256||''))reasons.push('attempt_receipt_sha256');
  if(!SHA_RE.test(receipt?.run_manifest_sha256||''))reasons.push('run_manifest_sha256');
  if(!getComputeProfile(receipt?.profile_id))reasons.push('profile_id');
  if(!ZERO_CASH_ORIGINS.has(receipt?.compute_origin)&&receipt?.compute_origin!==PAID_ORIGIN)reasons.push('compute_origin');
  if(receipt?.compute_origin===PAID_ORIGIN&&!SHA_RE.test(receipt?.manager_authorization_sha256||''))reasons.push('manager_authorization_sha256');
  if(receipt?.compute_origin!==PAID_ORIGIN&&receipt?.manager_authorization_sha256!==null)reasons.push('unexpected_manager_authorization_sha256');
  if(!exactKeys(receipt?.billing,BILLING_KEYS))reasons.push('billing_schema');
  else{
    for(const key of ['provider_rate_usd_per_gpu_hour','estimated_compute_cost_usd','egress_rate_usd_per_gib','estimated_egress_cost_usd','estimated_total_cost_usd']){
      if(!isCanonicalDecimal(receipt.billing[key]))reasons.push(`billing_${key}`);
    }
    for(const key of ['actual_billed_wall_seconds','actual_compute_cost_usd','actual_egress_cost_usd','actual_total_cost_usd']){
      if(receipt.billing[key]!==null&&!isCanonicalDecimal(receipt.billing[key]))reasons.push(`billing_${key}`);
    }
    for(const key of ['billing_granularity_seconds','billing_start_epoch_ms','process_end_epoch_ms','observed_billed_wall_seconds','artifact_egress_bytes']){
      if(!integer(receipt.billing[key]))reasons.push(`billing_${key}`);
    }
  }
  if(!exactKeys(receipt?.work,WORK_KEYS))reasons.push('work_schema');
  else{
    if(!integer(receipt.work.gpu_count,{min:1,max:64}))reasons.push('work_gpu_count');
    if(!isCanonicalDecimal(receipt.work.gpu_seconds))reasons.push('work_gpu_seconds');
    if(typeof receipt.work.work_counters_complete!=='boolean')reasons.push('work_counters_complete');
    for(const key of ['peak_vram_bytes','tokens_processed','tokens_generated','examples_processed']){
      const v=receipt.work[key];if(v!==null&&!integer(v,{min:key==='peak_vram_bytes'?1:0}))reasons.push(`work_${key}`);
    }
    if(receipt.work.work_counters_complete!==['peak_vram_bytes','tokens_processed','tokens_generated','examples_processed'].every(k=>receipt.work[k]!==null))reasons.push('work_counter_completeness_mismatch');
    if(!integer(receipt.work.retry_index,{min:0,max:3}))reasons.push('work_retry_index');
    if(!['success','failed'].includes(receipt.work.outcome))reasons.push('work_outcome');
  }
  if(!SHA_RE.test(receipt?.receipt_sha256||''))reasons.push('receipt_sha256');
  if(reasons.length===0&&!verifyP2SelfDigest(receipt))reasons.push('receipt_self_hash_mismatch');
  return Object.freeze({ok:reasons.length===0,reasons:Object.freeze(reasons)});
}

export function enforceAuthorizedBudget({authorization,billing}={}){
  const check=verifyManagerComputeAuthorization(authorization);
  const reasons=[];
  if(!check.ok)reasons.push(...check.reasons);
  if(!billing||!exactKeys(billing,BILLING_KEYS))reasons.push('billing_schema');
  if(check.ok&&billing){
    if(Number(billing.observed_billed_wall_seconds)>authorization.max_billed_seconds)reasons.push('billed_time_exceeds_authorization');
    if(billing.actual_billed_wall_seconds!==null&&Number(billing.actual_billed_wall_seconds)>authorization.max_billed_seconds)reasons.push('actual_billed_time_exceeds_authorization');
    if(Number(billing.estimated_total_cost_usd)>Number(authorization.max_total_cost_usd))reasons.push('estimated_cost_exceeds_authorization');
    if(billing.actual_total_cost_usd!==null&&Number(billing.actual_total_cost_usd)>Number(authorization.max_total_cost_usd))reasons.push('actual_cost_exceeds_authorization');
    if(Number(billing.provider_rate_usd_per_gpu_hour)>Number(authorization.max_hourly_rate_usd))reasons.push('hourly_rate_exceeds_authorization');
    if(billing.artifact_egress_bytes>authorization.max_artifact_egress_bytes)reasons.push('artifact_egress_exceeds_authorization');
  }
  return Object.freeze({ok:reasons.length===0,reasons:Object.freeze(reasons)});
}

export function buildVerifiedCandidateCostSummary({
  candidateArtifactManifestSha256,worker05EvaluationReceiptSha256,managerAcceptanceReceiptSha256,costReceipts,
}={}){
  if(!isSha256Hex(candidateArtifactManifestSha256))throw new TypeError('candidate_artifact_manifest_sha256');
  if(!isSha256Hex(worker05EvaluationReceiptSha256))throw new TypeError('worker05_evaluation_receipt_sha256');
  if(!isSha256Hex(managerAcceptanceReceiptSha256))throw new TypeError('manager_acceptance_receipt_sha256');
  if(!Array.isArray(costReceipts)||!costReceipts.length)throw new TypeError('cost_receipts');
  for(const r of costReceipts){const check=verifyComputeCostReceipt(r);if(!check.ok)throw new TypeError(`invalid_cost_receipt:${check.reasons.join(',')}`)}
  let gpu=0,billed=0,tokens=0,examples=0,egress=0,estimated=0,actual=0,actualComplete=true,incompleteWork=0;
  for(const r of costReceipts){
    gpu+=Number(r.work.gpu_seconds);
    billed+=Number(r.billing.actual_billed_wall_seconds??r.billing.observed_billed_wall_seconds);
    if(r.work.tokens_processed!==null)tokens+=r.work.tokens_processed;
    if(r.work.examples_processed!==null)examples+=r.work.examples_processed;
    if(!r.work.work_counters_complete)incompleteWork++;
    egress+=r.billing.artifact_egress_bytes;
    estimated+=Number(r.billing.estimated_total_cost_usd);
    if(r.billing.actual_total_cost_usd===null)actualComplete=false;else actual+=Number(r.billing.actual_total_cost_usd);
  }
  const draft={
    schema_version:1,
    summary_kind:VERIFIED_CANDIDATE_COST_KIND,
    hash_profile:P2_HASH_PROFILE,
    candidate_artifact_manifest_sha256:candidateArtifactManifestSha256,
    worker05_evaluation_receipt_sha256:worker05EvaluationReceiptSha256,
    manager_acceptance_receipt_sha256:managerAcceptanceReceiptSha256,
    attempt_cost_receipt_sha256s:costReceipts.map(r=>r.receipt_sha256).sort(),
    attempts:costReceipts.length,
    gpu_seconds_total:canonicalSeconds(gpu),
    billed_wall_seconds_total:canonicalSeconds(billed),
    tokens_processed_total:tokens,
    examples_processed_total:examples,
    work_counter_incomplete_attempts:incompleteWork,
    artifact_egress_bytes_total:egress,
    estimated_total_cost_usd:money(estimated),
    actual_total_cost_usd:actualComplete?money(actual):null,
    cost_basis:actualComplete?'provider_actual':'estimated_pending_provider_actual',
  };
  return Object.freeze({...draft,summary_sha256:sha256Canonical(draft)});
}

export function verifyVerifiedCandidateCostSummary(summary){
  const reasons=[];
  if(!exactKeys(summary,SUMMARY_KEYS))reasons.push('summary_schema');
  if(summary?.schema_version!==1)reasons.push('schema_version');
  if(summary?.summary_kind!==VERIFIED_CANDIDATE_COST_KIND)reasons.push('summary_kind');
  if(summary?.hash_profile!==P2_HASH_PROFILE)reasons.push('hash_profile');
  for(const key of ['candidate_artifact_manifest_sha256','worker05_evaluation_receipt_sha256','manager_acceptance_receipt_sha256','summary_sha256'])if(!SHA_RE.test(summary?.[key]||''))reasons.push(key);
  if(!Array.isArray(summary?.attempt_cost_receipt_sha256s)||!summary.attempt_cost_receipt_sha256s.length||summary.attempt_cost_receipt_sha256s.some(x=>!SHA_RE.test(x)))reasons.push('attempt_cost_receipt_sha256s');
  for(const key of ['attempts','tokens_processed_total','examples_processed_total','work_counter_incomplete_attempts','artifact_egress_bytes_total'])if(!integer(summary?.[key]))reasons.push(key);
  for(const key of ['gpu_seconds_total','billed_wall_seconds_total','estimated_total_cost_usd'])if(!isCanonicalDecimal(summary?.[key]))reasons.push(key);
  if(summary?.actual_total_cost_usd!==null&&!isCanonicalDecimal(summary.actual_total_cost_usd))reasons.push('actual_total_cost_usd');
  if(!['provider_actual','estimated_pending_provider_actual'].includes(summary?.cost_basis))reasons.push('cost_basis');
  if(reasons.length===0&&!verifyP2SelfDigest(summary,{digestField:'summary_sha256'}))reasons.push('summary_self_hash_mismatch');
  return Object.freeze({ok:reasons.length===0,reasons:Object.freeze(reasons)});
}
