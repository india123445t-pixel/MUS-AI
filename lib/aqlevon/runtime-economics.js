import {buildApprovedTruthAuthority,resolveAttemptVerification,verifyRuntimeAttemptReceipt} from './runtime-receipts.js';

function finiteNonNegative(value){
  if(value===null||value===undefined||value==='')return null;
  const n=Number(value);
  return Number.isFinite(n)&&n>=0?n:null;
}

function integerNonNegative(value){
  const n=finiteNonNegative(value);
  return n===null?null:Math.floor(n);
}

function round(value,digits=6){
  if(value===null||value===undefined||!Number.isFinite(Number(value)))return null;
  const factor=10**digits;
  return Math.round(Number(value)*factor)/factor;
}

export function normalizeBoundedInteger(value,{defaultValue=1,min=1,max=16}={}){
  const fallback=Math.max(min,Math.min(max,Math.floor(Number(defaultValue))||min));
  if(value===null||value===undefined||String(value).trim()==='')return fallback;
  const n=Number(value);
  if(!Number.isFinite(n))return fallback;
  return Math.max(min,Math.min(max,Math.floor(n)));
}

export function parseStrictBoundedInteger(value,{defaultValue=null,min=1,max=Number.MAX_SAFE_INTEGER}={}){
  if(value===null||value===undefined||String(value).trim()==='')return defaultValue;
  const raw=String(value).trim();
  if(!/^\d+$/.test(raw))return null;
  const n=Number(raw);
  if(!Number.isSafeInteger(n)||n<min||n>max)return null;
  return n;
}

export function sanitizeEndpointForLog(raw){
  try{
    const u=new URL(String(raw));
    if(!['http:','https:'].includes(u.protocol))return 'invalid-endpoint';
    return `${u.protocol}//${u.hostname}${u.port?`:${u.port}`:''}`;
  }catch{return 'invalid-endpoint'}
}

export function normalizeOpenAIUsage(usage={}){
  const promptTokens=finiteNonNegative(usage?.prompt_tokens??usage?.input_tokens);
  const completionTokens=finiteNonNegative(usage?.completion_tokens??usage?.output_tokens);
  let totalTokens=finiteNonNegative(usage?.total_tokens);
  if(totalTokens===null&&promptTokens!==null&&completionTokens!==null)totalTokens=promptTokens+completionTokens;
  const cachedRaw=finiteNonNegative(usage?.prompt_tokens_details?.cached_tokens??usage?.input_tokens_details?.cached_tokens??usage?.cached_prompt_tokens);
  const cachedPromptTokens=promptTokens!==null&&cachedRaw!==null?Math.min(promptTokens,cachedRaw):cachedRaw;
  const reasoningTokens=finiteNonNegative(usage?.completion_tokens_details?.reasoning_tokens??usage?.output_tokens_details?.reasoning_tokens??usage?.reasoning_tokens);
  return Object.freeze({
    prompt_tokens:promptTokens,
    completion_tokens:completionTokens,
    total_tokens:totalTokens,
    cached_prompt_tokens:cachedPromptTokens,
    reasoning_tokens:reasoningTokens,
  });
}

export function buildRuntimeAccounting({
  elapsedMs,
  usage,
  computeDevice='unknown',
  gpuCount=null,
  gpuPowerWatts=null,
  gpuHourlyUsd=null,
}={}){
  const elapsed=finiteNonNegative(elapsedMs);
  const elapsedSeconds=elapsed===null?null:elapsed/1000;
  const gpus=integerNonNegative(gpuCount);
  const powerPerGpu=finiteNonNegative(gpuPowerWatts);
  const hourlyPerGpu=finiteNonNegative(gpuHourlyUsd);
  const tokens=normalizeOpenAIUsage(usage);
  const allocatedGpuSeconds=elapsedSeconds!==null&&gpus!==null?elapsedSeconds*gpus:null;
  const completionTokensPerSecond=elapsedSeconds>0&&tokens.completion_tokens!==null?tokens.completion_tokens/elapsedSeconds:null;
  const completionTokensPerGpuSecond=allocatedGpuSeconds>0&&tokens.completion_tokens!==null?tokens.completion_tokens/allocatedGpuSeconds:null;
  const cachedPromptRatio=tokens.prompt_tokens>0&&tokens.cached_prompt_tokens!==null?tokens.cached_prompt_tokens/tokens.prompt_tokens:null;
  const estimatedEnergyWh=allocatedGpuSeconds!==null&&powerPerGpu!==null?allocatedGpuSeconds*powerPerGpu/3600:null;
  const estimatedGpuCostUsd=allocatedGpuSeconds!==null&&hourlyPerGpu!==null?allocatedGpuSeconds*hourlyPerGpu/3600:null;
  return Object.freeze({
    schema:'aqlevon-runtime-metrics-v1',
    elapsed_ms:round(elapsed,3),
    compute_device:String(computeDevice||'unknown').slice(0,64),
    gpu_count:gpus,
    allocated_gpu_seconds:round(allocatedGpuSeconds),
    prompt_tokens:tokens.prompt_tokens,
    completion_tokens:tokens.completion_tokens,
    total_tokens:tokens.total_tokens,
    cached_prompt_tokens:tokens.cached_prompt_tokens,
    reasoning_tokens:tokens.reasoning_tokens,
    cached_prompt_ratio:round(cachedPromptRatio),
    completion_tokens_per_second:round(completionTokensPerSecond),
    completion_tokens_per_gpu_second:round(completionTokensPerGpuSecond),
    configured_gpu_power_watts:powerPerGpu,
    configured_gpu_hourly_usd:hourlyPerGpu,
    estimated_energy_wh:round(estimatedEnergyWh),
    estimated_gpu_cost_usd:round(estimatedGpuCostUsd,8),
  });
}

function invalidEfficiencySummary(attempts,reasons){
  return Object.freeze({
    schema:'aqlevon-verified-efficiency-summary-v2',
    status:'INVALID',
    truth_policy:'receipt_join_only',
    invalid_reason_codes:Object.freeze([...new Set(reasons)].sort()),
    attempts,
    transport_successes:null,
    transport_failures:null,
    verified_successes:null,
    verified_by_evaluation:null,
    verified_by_objective:null,
    truth_conflicts:null,
    unapproved_truth_receipts_ignored:null,
    allocated_gpu_seconds_total:null,
    gpu_seconds_per_verified_success:null,
    estimated_energy_wh_total:null,
    estimated_energy_wh_per_verified_success:null,
    estimated_gpu_cost_usd_total:null,
    estimated_gpu_cost_usd_per_verified_success:null,
  });
}

export function summarizeVerifiedEfficiency(attemptReceipts=[],truth={}){
  if(!Array.isArray(attemptReceipts))return invalidEfficiencySummary(0,['attempt_receipts_type']);
  const invalid=[];
  for(const receipt of attemptReceipts){
    const check=verifyRuntimeAttemptReceipt(receipt);
    if(!check.ok)invalid.push(...check.reasons.map(r=>`attempt_${r}`));
  }
  const authority=buildApprovedTruthAuthority(truth);
  if(!authority.ok)invalid.push(...authority.reasons);
  if(invalid.length)return invalidEfficiencySummary(attemptReceipts.length,invalid);

  let verifiedSuccesses=0,verifiedByEvaluation=0,verifiedByObjective=0,truthConflicts=0;
  let transportSuccesses=0,transportFailures=0;
  let totalGpuSeconds=0,seenGpuSeconds=false;
  let totalEnergyWh=0,seenEnergy=false;
  let totalCostUsd=0,seenCost=false;

  for(const receipt of attemptReceipts){
    const metrics=receipt.runtime_metrics;
    if(receipt.transport_outcome.status==='success')transportSuccesses++;else transportFailures++;
    const decision=resolveAttemptVerification(receipt,authority);
    if(decision.conflict)truthConflicts++;
    if(decision.verified){
      verifiedSuccesses++;
      if(decision.source==='evaluation_decision')verifiedByEvaluation++;
      if(decision.source==='objective_verifier')verifiedByObjective++;
    }
    const gpuSeconds=finiteNonNegative(metrics?.allocated_gpu_seconds);
    const energyWh=finiteNonNegative(metrics?.estimated_energy_wh);
    const costUsd=finiteNonNegative(metrics?.estimated_gpu_cost_usd);
    if(gpuSeconds!==null){totalGpuSeconds+=gpuSeconds;seenGpuSeconds=true}
    if(energyWh!==null){totalEnergyWh+=energyWh;seenEnergy=true}
    if(costUsd!==null){totalCostUsd+=costUsd;seenCost=true}
  }

  return Object.freeze({
    schema:'aqlevon-verified-efficiency-summary-v2',
    status:'VALID',
    truth_policy:'receipt_join_only',
    invalid_reason_codes:Object.freeze([]),
    attempts:attemptReceipts.length,
    transport_successes:transportSuccesses,
    transport_failures:transportFailures,
    verified_successes:verifiedSuccesses,
    verified_by_evaluation:verifiedByEvaluation,
    verified_by_objective:verifiedByObjective,
    truth_conflicts:truthConflicts,
    unapproved_truth_receipts_ignored:authority.ignoredUnapproved,
    allocated_gpu_seconds_total:seenGpuSeconds?round(totalGpuSeconds):null,
    gpu_seconds_per_verified_success:seenGpuSeconds&&verifiedSuccesses>0?round(totalGpuSeconds/verifiedSuccesses):null,
    estimated_energy_wh_total:seenEnergy?round(totalEnergyWh):null,
    estimated_energy_wh_per_verified_success:seenEnergy&&verifiedSuccesses>0?round(totalEnergyWh/verifiedSuccesses):null,
    estimated_gpu_cost_usd_total:seenCost?round(totalCostUsd,8):null,
    estimated_gpu_cost_usd_per_verified_success:seenCost&&verifiedSuccesses>0?round(totalCostUsd/verifiedSuccesses,8):null,
  });
}
