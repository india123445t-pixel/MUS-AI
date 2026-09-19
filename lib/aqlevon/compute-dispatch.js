import path from 'node:path';
import {
  P2_HASH_PROFILE,
  canonicalDecimalString,
  isSha256Hex,
  sha256Canonical,
  verifyP2SelfDigest,
} from './runtime-receipts.js';

export const P3_COMPUTE_TASK_ID='P3-A06-COMPUTE-DISPATCH';
export const COMPUTE_ATTEMPT_RECEIPT_KIND='AQLEVON_COMPUTE_ATTEMPT_RECEIPT_V1';
export const PAYLOAD_TELEMETRY_SCHEMA='aqlevon-p3-payload-telemetry-v1';

const PROFILE_ROWS={
  'g1-1x80-bf16-lora':{
    purpose:'G1/R0-A canonical BF16 LoRA truth lane',gpu_count:1,min_vram_mib_each:78000,
    planned_vram_ceiling_mib_each:null,launcher:'direct',precision_policy:'bf16_lora_only',
  },
  'g1-2x48-fsdp2':{
    purpose:'G1/R0-A BF16 LoRA FSDP2 fallback',gpu_count:2,min_vram_mib_each:45000,
    planned_vram_ceiling_mib_each:null,launcher:'torchrun_fsdp2',precision_policy:'bf16_lora_only',
  },
  'g1-4x24-fsdp2':{
    purpose:'G1/R0-A BF16 LoRA FSDP2 fallback',gpu_count:4,min_vram_mib_each:22000,
    planned_vram_ceiling_mib_each:null,launcher:'torchrun_fsdp2',precision_policy:'bf16_lora_only',
  },
  'b07-e0-1x8to12':{
    purpose:'B07-E0 small-model breakthrough falsifier',gpu_count:1,min_vram_mib_each:7800,
    planned_vram_ceiling_mib_each:13000,launcher:'direct',precision_policy:'small_model_experiment',
  },
  'rl-qwen38-1x80-ms-swift-colocate':{
    purpose:'Later online-RL systems smoke: ms-swift + vLLM colocate + LoRA-only sync',gpu_count:1,min_vram_mib_each:78000,
    planned_vram_ceiling_mib_each:null,launcher:'ms_swift_colocate',precision_policy:'bf16_lora_only',
  },
};

export const COMPUTE_PROFILES=Object.freeze(Object.fromEntries(
  Object.entries(PROFILE_ROWS).map(([id,row])=>[id,Object.freeze({
    schema:'aqlevon-p3-compute-profile-v1',profile_id:id,paid_compute_authorized:false,...row,
  })])
));

const TOP_KEYS=new Set([
  'schema_version','receipt_kind','hash_profile','task_id','attempt_id','profile_id','run_manifest_sha256',
  'payload_identity','compute_origin','hardware','telemetry','outcome','receipt_sha256',
]);
const PAYLOAD_KEYS=new Set(['executable','argc','argv_sha256']);
const HARDWARE_KEYS=new Set(['gpu_indices','gpu_models','gpu_vram_mib']);
const TELEMETRY_KEYS=new Set([
  'telemetry_complete','elapsed_ms','allocated_gpu_seconds','peak_vram_bytes','tokens_processed','tokens_generated',
  'attempt_retry_index','device_memory_sample_peak_mib','sample_interval_ms','peak_vram_source','token_source',
]);
const OUTCOME_KEYS=new Set(['status','exit_code','signal','failure_code']);
const SAFE_ORIGINS=new Set(['owned','donated','free']);
const SHA_RE=/^[0-9a-f]{64}$/;

function exactKeys(value,allowed){
  if(!value||typeof value!=='object'||Array.isArray(value))return false;
  const keys=Object.keys(value);return keys.length===allowed.size&&keys.every(k=>allowed.has(k));
}
function id(value){return typeof value==='string'&&value.length>0&&value.length<=256}
function int(value,{min=0,max=Number.MAX_SAFE_INTEGER}={}){return Number.isSafeInteger(value)&&value>=min&&value<=max}

export function getComputeProfile(profileId){return COMPUTE_PROFILES[String(profileId)]||null}

export function parseGpuIndices(raw){
  if(Array.isArray(raw))raw=raw.join(',');
  if(typeof raw!=='string'||!raw.trim())return null;
  const parts=raw.split(',').map(x=>x.trim());
  if(parts.some(x=>!/^d+$/.test(x)))return null;
  const values=parts.map(Number);
  if(values.some(x=>!Number.isSafeInteger(x)||x<0)||new Set(values).size!==values.length)return null;
  return values;
}

export function parseNvidiaSmiInventory(text){
  if(typeof text!=='string')return [];
  const rows=[];
  for(const rawLine of text.split(/?
/)){
    const line=rawLine.trim();if(!line)continue;
    const parts=line.split('|').map(x=>x.trim());
    if(parts.length!==3||!/^d+$/.test(parts[0])||!/^d+$/.test(parts[2]))continue;
    const index=Number(parts[0]),memory_mib=Number(parts[2]);
    if(!Number.isSafeInteger(index)||!Number.isSafeInteger(memory_mib)||memory_mib<=0||!parts[1])continue;
    rows.push(Object.freeze({index,name:parts[1].slice(0,160),memory_mib}));
  }
  return rows;
}

export function assessHardware(profileId,inventory,gpuIndices){
  const profile=getComputeProfile(profileId);const reasons=[];const advisories=[];
  if(!profile)return Object.freeze({ok:false,reasons:['unknown_profile'],advisories,selected:[]});
  const indices=Array.isArray(gpuIndices)?gpuIndices:parseGpuIndices(String(gpuIndices??''));
  if(!indices){reasons.push('invalid_gpu_indices');return Object.freeze({ok:false,reasons,advisories,selected:[]})}
  if(indices.length!==profile.gpu_count)reasons.push('gpu_count_mismatch');
  const byIndex=new Map((Array.isArray(inventory)?inventory:[]).map(g=>[g.index,g]));
  const selected=[];
  for(const index of indices){const gpu=byIndex.get(index);if(!gpu)reasons.push(`gpu_missing_${index}`);else selected.push(gpu)}
  for(const gpu of selected){
    if(gpu.memory_mib<profile.min_vram_mib_each)reasons.push(`gpu_vram_below_floor_${gpu.index}`);
    if(profile.planned_vram_ceiling_mib_each!==null&&gpu.memory_mib>profile.planned_vram_ceiling_mib_each)advisories.push(`gpu_above_planning_class_${gpu.index}`);
  }
  return Object.freeze({ok:reasons.length===0,reasons:Object.freeze(reasons),advisories:Object.freeze(advisories),selected:Object.freeze(selected)});
}

export function validateExecutionAuthorization({authorized,computeOrigin}={}){
  const origin=String(computeOrigin||'').trim().toLowerCase();
  const reasons=[];
  if(String(authorized)!=='1')reasons.push('gpu_execution_not_authorized');
  if(!SAFE_ORIGINS.has(origin))reasons.push('compute_origin_not_zero_cash');
  return Object.freeze({ok:reasons.length===0,compute_origin:SAFE_ORIGINS.has(origin)?origin:null,reasons:Object.freeze(reasons)});
}

export function payloadIdentity(argv=[]){
  if(!Array.isArray(argv)||argv.length===0||typeof argv[0]!=='string'||!argv[0])throw new TypeError('payload_argv_required');
  return Object.freeze({
    executable:path.basename(argv[0]).slice(0,120),
    argc:argv.length,
    argv_sha256:sha256Canonical(argv.map(String)),
  });
}

export function parsePayloadTelemetry(value){
  const reasons=[];let raw=value;
  if(typeof value==='string'){try{raw=JSON.parse(value)}catch{return {ok:false,reasons:['telemetry_json_parse'],telemetry:null}}}
  if(!raw||typeof raw!=='object'||Array.isArray(raw))return {ok:false,reasons:['telemetry_object'],telemetry:null};
  if(raw.schema!==PAYLOAD_TELEMETRY_SCHEMA)reasons.push('telemetry_schema');
  const peak=raw.peak_vram_bytes,processed=raw.tokens_processed,generated=raw.tokens_generated??0;
  if(!int(peak,{min:1}))reasons.push('peak_vram_bytes');
  if(!int(processed))reasons.push('tokens_processed');
  if(!int(generated))reasons.push('tokens_generated');
  return {ok:reasons.length===0,reasons,telemetry:reasons.length?null:Object.freeze({
    peak_vram_bytes:peak,tokens_processed:processed,tokens_generated:generated,
  })};
}

function cleanSignal(value){return value===null?null:(typeof value==='string'&&/^[A-Z0-9]+$/.test(value)&&value.length<=24?value:null)}
function cleanFailure(value){return value===null?null:(typeof value==='string'&&/^[a-z0-9_:-]+$/.test(value)&&value.length<=96?value:null)}

export function buildComputeAttemptReceipt({
  attemptId,profileId,runManifestSha256,payloadArgv,computeOrigin,hardware,elapsedMs,
  payloadTelemetry=null,retryIndex=0,deviceMemorySamplePeakMib=[],sampleIntervalMs=250,
  status,exitCode=null,signal=null,failureCode=null,
}={}){
  const profile=getComputeProfile(profileId);
  if(!profile)throw new TypeError('unknown_profile');
  if(!id(attemptId))throw new TypeError('attempt_id');
  if(!isSha256Hex(runManifestSha256)||runManifestSha256!==runManifestSha256.toLowerCase())throw new TypeError('run_manifest_sha256');
  if(!SAFE_ORIGINS.has(String(computeOrigin)))throw new TypeError('compute_origin');
  if(!int(Math.round(elapsedMs),{min:0}))throw new TypeError('elapsed_ms');
  if(!int(retryIndex,{min:0,max:3}))throw new TypeError('retry_index');
  if(!int(sampleIntervalMs,{min:25,max:10000}))throw new TypeError('sample_interval_ms');
  const hw=assessHardware(profileId,hardware?.inventory||[],hardware?.gpu_indices||[]);
  if(!hw.ok)throw new TypeError(`hardware:${hw.reasons.join(',')}`);
  const parsedTelemetry=payloadTelemetry===null?{ok:false,reasons:['telemetry_missing'],telemetry:null}:parsePayloadTelemetry(payloadTelemetry);
  const elapsed=Math.round(elapsedMs);
  const gpuMs=elapsed*profile.gpu_count;
  const outcomeStatus=String(status);
  if(!['success','failed'].includes(outcomeStatus))throw new TypeError('outcome_status');
  const code=exitCode===null?null:Number(exitCode);
  if(code!==null&&!int(code,{min:0,max:255}))throw new TypeError('exit_code');
  const sig=cleanSignal(signal);if(signal!==null&&sig===null)throw new TypeError('signal');
  const failure=cleanFailure(failureCode);if(failureCode!==null&&failure===null)throw new TypeError('failure_code');
  if(outcomeStatus==='success'&&(code!==0||sig!==null||failure!==null))throw new TypeError('success_outcome_inconsistent');
  if(outcomeStatus==='failed'&&failure===null)throw new TypeError('failed_outcome_requires_code');
  const samples=Array.isArray(deviceMemorySamplePeakMib)?deviceMemorySamplePeakMib:[];
  if(samples.length!==profile.gpu_count||samples.some(x=>!int(x,{min:0})))throw new TypeError('device_memory_sample_peak_mib');
  const t=parsedTelemetry.telemetry;
  const draft={
    schema_version:1,
    receipt_kind:COMPUTE_ATTEMPT_RECEIPT_KIND,
    hash_profile:P2_HASH_PROFILE,
    task_id:P3_COMPUTE_TASK_ID,
    attempt_id:String(attemptId),
    profile_id:profileId,
    run_manifest_sha256:runManifestSha256,
    payload_identity:payloadIdentity(payloadArgv),
    compute_origin:String(computeOrigin),
    hardware:{
      gpu_indices:hw.selected.map(g=>g.index),
      gpu_models:hw.selected.map(g=>g.name),
      gpu_vram_mib:hw.selected.map(g=>g.memory_mib),
    },
    telemetry:{
      telemetry_complete:parsedTelemetry.ok,
      elapsed_ms:elapsed,
      allocated_gpu_seconds:canonicalDecimalString(gpuMs/1000),
      peak_vram_bytes:t?.peak_vram_bytes??null,
      tokens_processed:t?.tokens_processed??null,
      tokens_generated:t?.tokens_generated??null,
      attempt_retry_index:retryIndex,
      device_memory_sample_peak_mib:samples,
      sample_interval_ms:sampleIntervalMs,
      peak_vram_source:t?'payload_cuda_peak_counter':'unavailable',
      token_source:t?'payload_exact_counter':'unavailable',
    },
    outcome:{status:outcomeStatus,exit_code:code,signal:sig,failure_code:failure},
  };
  return Object.freeze({...draft,receipt_sha256:sha256Canonical(draft)});
}

export function verifyComputeAttemptReceipt(receipt){
  const reasons=[];
  if(!exactKeys(receipt,TOP_KEYS))reasons.push('top_level_schema');
  if(receipt?.schema_version!==1)reasons.push('schema_version');
  if(receipt?.receipt_kind!==COMPUTE_ATTEMPT_RECEIPT_KIND)reasons.push('receipt_kind');
  if(receipt?.hash_profile!==P2_HASH_PROFILE)reasons.push('hash_profile');
  if(receipt?.task_id!==P3_COMPUTE_TASK_ID)reasons.push('task_id');
  if(!id(receipt?.attempt_id))reasons.push('attempt_id');
  if(!getComputeProfile(receipt?.profile_id))reasons.push('profile_id');
  if(!SHA_RE.test(receipt?.run_manifest_sha256||''))reasons.push('run_manifest_sha256');
  if(!exactKeys(receipt?.payload_identity,PAYLOAD_KEYS))reasons.push('payload_identity_schema');
  else{
    if(!id(receipt.payload_identity.executable))reasons.push('payload_executable');
    if(!int(receipt.payload_identity.argc,{min:1}))reasons.push('payload_argc');
    if(!SHA_RE.test(receipt.payload_identity.argv_sha256))reasons.push('payload_argv_sha256');
  }
  if(!SAFE_ORIGINS.has(receipt?.compute_origin))reasons.push('compute_origin');
  if(!exactKeys(receipt?.hardware,HARDWARE_KEYS))reasons.push('hardware_schema');
  else{
    const profile=getComputeProfile(receipt.profile_id);
    for(const key of HARDWARE_KEYS)if(!Array.isArray(receipt.hardware[key]))reasons.push(`hardware_${key}`);
    if(profile&&receipt.hardware.gpu_indices?.length!==profile.gpu_count)reasons.push('hardware_gpu_count');
    if(receipt.hardware.gpu_indices?.some(x=>!int(x)))reasons.push('hardware_gpu_indices');
    if(receipt.hardware.gpu_vram_mib?.some(x=>!int(x,{min:1})))reasons.push('hardware_gpu_vram_mib');
    if(receipt.hardware.gpu_models?.some(x=>!id(x)))reasons.push('hardware_gpu_models');
  }
  if(!exactKeys(receipt?.telemetry,TELEMETRY_KEYS))reasons.push('telemetry_schema');
  else{
    const t=receipt.telemetry;
    if(typeof t.telemetry_complete!=='boolean')reasons.push('telemetry_complete');
    if(!int(t.elapsed_ms))reasons.push('telemetry_elapsed_ms');
    if(typeof t.allocated_gpu_seconds!=='string'||Number(t.allocated_gpu_seconds)<0||!Number.isFinite(Number(t.allocated_gpu_seconds)))reasons.push('telemetry_gpu_seconds');
    if(t.telemetry_complete){
      if(!int(t.peak_vram_bytes,{min:1}))reasons.push('telemetry_peak_vram');
      if(!int(t.tokens_processed))reasons.push('telemetry_tokens_processed');
      if(!int(t.tokens_generated))reasons.push('telemetry_tokens_generated');
      if(t.peak_vram_source!=='payload_cuda_peak_counter')reasons.push('telemetry_peak_source');
      if(t.token_source!=='payload_exact_counter')reasons.push('telemetry_token_source');
    }else if(t.peak_vram_bytes!==null||t.tokens_processed!==null||t.tokens_generated!==null)reasons.push('telemetry_incomplete_values');
    if(!int(t.attempt_retry_index,{min:0,max:3}))reasons.push('telemetry_retry_index');
    if(!Array.isArray(t.device_memory_sample_peak_mib)||t.device_memory_sample_peak_mib.some(x=>!int(x)))reasons.push('telemetry_memory_samples');
    if(!int(t.sample_interval_ms,{min:25,max:10000}))reasons.push('telemetry_sample_interval');
  }
  if(!exactKeys(receipt?.outcome,OUTCOME_KEYS))reasons.push('outcome_schema');
  else{
    if(!['success','failed'].includes(receipt.outcome.status))reasons.push('outcome_status');
    if(receipt.outcome.exit_code!==null&&!int(receipt.outcome.exit_code,{min:0,max:255}))reasons.push('outcome_exit_code');
    if(receipt.outcome.signal!==null&&cleanSignal(receipt.outcome.signal)===null)reasons.push('outcome_signal');
    if(receipt.outcome.failure_code!==null&&cleanFailure(receipt.outcome.failure_code)===null)reasons.push('outcome_failure_code');
    if(receipt.outcome.status==='success'&&(receipt.outcome.exit_code!==0||receipt.outcome.signal!==null||receipt.outcome.failure_code!==null))reasons.push('outcome_success_inconsistent');
    if(receipt.outcome.status==='failed'&&receipt.outcome.failure_code===null)reasons.push('outcome_failed_missing_code');
  }
  if(!SHA_RE.test(receipt?.receipt_sha256||''))reasons.push('receipt_sha256');
  if(reasons.length===0&&!verifyP2SelfDigest(receipt))reasons.push('receipt_self_hash_mismatch');
  return Object.freeze({ok:reasons.length===0,reasons:Object.freeze(reasons)});
}

export function buildMsSwiftColocateLoRAArgs({
  datasetPath,rewardPluginPath,rewardFunctions,loraRank=8,model='Qwen/Qwen3.8-27B',extraArgs=[],
}={}){
  if(model!=='Qwen/Qwen3.8-27B')throw new TypeError('canonical_qwen38_model_required');
  if(typeof datasetPath!=='string'||!datasetPath.trim())throw new TypeError('dataset_path_required');
  if(typeof rewardPluginPath!=='string'||!rewardPluginPath.trim())throw new TypeError('reward_plugin_path_required');
  const rewards=Array.isArray(rewardFunctions)?rewardFunctions.map(String).filter(Boolean):[];
  if(!rewards.length||rewards.some(x=>!/^[A-Za-z0-9_.-]+$/.test(x)))throw new TypeError('reward_functions_required');
  const rank=Number(loraRank);if(!Number.isSafeInteger(rank)||rank<1||rank>256)throw new TypeError('lora_rank');
  if(!Array.isArray(extraArgs)||extraArgs.some(x=>typeof x!=='string'))throw new TypeError('extra_args');
  const forbidden=/qlora|4bit|4-bit|load_in_4bit|quantization/i;
  if(extraArgs.some(x=>forbidden.test(x)))throw new TypeError('canonical_bf16_lane_forbids_quantization_flags');
  return Object.freeze([
    'swift','rlhf','--rlhf_type','grpo','--model',model,'--dataset',datasetPath,
    '--tuner_type','lora','--lora_rank',String(rank),
    '--external_plugins',rewardPluginPath,'--reward_funcs',...rewards,
    '--use_vllm','true','--vllm_mode','colocate','--vllm_enable_lora','true','--vllm_max_lora_rank',String(rank),
    '--sleep_level','1','--offload_optimizer','true','--offload_model','true',
    ...extraArgs,
  ]);
}
