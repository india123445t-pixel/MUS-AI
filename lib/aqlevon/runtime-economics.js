import {resolveAttemptVerification,validateRuntimeAttemptReceipt} from './runtime-attempt-receipt.js';

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

export function summarizeVerifiedEfficiency(receipts=[],{evaluationDecisionReceipts=[],objectiveVerifierApprovals=[],verificationJoins=[]}={}){
  const attempts=Array.isArray(receipts)?receipts:[];
  const invalid=[];
  for(let index=0;index<attempts.length;index++){
    const check=validateRuntimeAttemptReceipt(attempts[index]);
    if(!check.valid)invalid.push({index,errors:check.errors});
  }
  if(invalid.length){
    return Object.freeze({
      status:'INVALID',
      attempts:attempts.length,
      verified_successes:0,
      invalid_attempt_receipts:invalid,
      ignored_legacy_verified_flags:attempts.filter(x=>x?.verified===true).length,
      allocated_gpu_seconds_total:null,
      gpu_seconds_per_verified_success:null,
      estimated_energy_wh_total:null,
      estimated_energy_wh_per_verified_success:null,
      estimated_gpu_cost_usd_total:null,
      estimated_gpu_cost_usd_per_verified_success:null,
    });
  }

  let verifiedSuccesses=0;
  let totalGpuSeconds=0,seenGpuSeconds=false;
  let totalEnergyWh=0,seenEnergy=false;
  let totalCostUsd=0,seenCost=false;
  let evalVerified=0,objectiveVerified=0;
  for(const receipt of attempts){
    const metrics=receipt.runtime_metrics;
    const gpuSeconds=finiteNonNegative(metrics?.allocated_gpu_seconds);
    const energyWh=finiteNonNegative(metrics?.estimated_energy_wh);
    const costUsd=finiteNonNegative(metrics?.estimated_gpu_cost_usd);
    if(gpuSeconds!==null){totalGpuSeconds+=gpuSeconds;seenGpuSeconds=true}
    if(energyWh!==null){totalEnergyWh+=energyWh;seenEnergy=true}
    if(costUsd!==null){totalCostUsd+=costUsd;seenCost=true}
    const verification=resolveAttemptVerification(receipt,{evaluationDecisionReceipts,objectiveVerifierApprovals,verificationJoins});
    if(verification.verified){
      verifiedSuccesses++;
      if(verification.source==='evaluation_decision')evalVerified++;
      else if(verification.source==='objective_verifier')objectiveVerified++;
    }
  }
  return Object.freeze({
    status:'VALID',
    attempts:attempts.length,
    verified_successes:verifiedSuccesses,
    unverified_attempts:attempts.length-verifiedSuccesses,
    verification_sources:{evaluation_decision:evalVerified,objective_verifier:objectiveVerified},
    ignored_legacy_verified_flags:attempts.filter(x=>x?.verified===true).length,
    allocated_gpu_seconds_total:seenGpuSeconds?round(totalGpuSeconds):null,
    gpu_seconds_per_verified_success:seenGpuSeconds&&verifiedSuccesses>0?round(totalGpuSeconds/verifiedSuccesses):null,
    estimated_energy_wh_total:seenEnergy?round(totalEnergyWh):null,
    estimated_energy_wh_per_verified_success:seenEnergy&&verifiedSuccesses>0?round(totalEnergyWh/verifiedSuccesses):null,
    estimated_gpu_cost_usd_total:seenCost?round(totalCostUsd,8):null,
    estimated_gpu_cost_usd_per_verified_success:seenCost&&verifiedSuccesses>0?round(totalCostUsd/verifiedSuccesses,8):null,
  });
}
