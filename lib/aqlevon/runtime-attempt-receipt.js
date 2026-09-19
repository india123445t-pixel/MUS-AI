import {createHash,randomUUID} from 'node:crypto';

export const RUNTIME_ATTEMPT_RECEIPT_KIND='AQLEVON_RUNTIME_ATTEMPT_RECEIPT_V1';
export const EVALUATION_DECISION_RECEIPT_KIND='AQLEVON_EVALUATION_DECISION_RECEIPT_V1';

export function isSha256(value){return /^[0-9a-f]{64}$/i.test(String(value||''))}

function canonicalize(value){
  if(value===null||typeof value==='string'||typeof value==='boolean')return value;
  if(typeof value==='number'){
    if(!Number.isFinite(value))throw new TypeError('canonical_non_finite_number');
    return Object.is(value,-0)?0:value;
  }
  if(Array.isArray(value))return value.map(canonicalize);
  if(typeof value==='object'){
    const out={};
    for(const key of Object.keys(value).sort()){
      const child=value[key];
      if(child===undefined)continue;
      out[key]=canonicalize(child);
    }
    return out;
  }
  throw new TypeError('canonical_unsupported_type');
}

export function canonicalJson(value){return JSON.stringify(canonicalize(value))}
export function sha256Canonical(value){return createHash('sha256').update(canonicalJson(value)).digest('hex')}
export function sha256Text(value){return createHash('sha256').update(String(value??'')).digest('hex')}

function safeId(value,field){
  const s=String(value||'').trim();
  if(!s||s.length>200||/[\r\n\0]/.test(s))throw new TypeError(`invalid_${field}`);
  return s;
}

function requireSha(value,field){
  const s=String(value||'').toLowerCase();
  if(!isSha256(s))throw new TypeError(`invalid_${field}`);
  return s;
}

function finiteNonNegativeOrNull(value,field){
  if(value===null||value===undefined)return null;
  const n=Number(value);
  if(!Number.isFinite(n)||n<0)throw new TypeError(`invalid_${field}`);
  return n;
}

function normalizeRuntimeMetrics(metrics){
  if(!metrics||typeof metrics!=='object'||Array.isArray(metrics))throw new TypeError('invalid_runtime_metrics');
  if(metrics.schema!=='aqlevon-runtime-metrics-v1')throw new TypeError('unsupported_runtime_metrics_schema');
  const normalized={
    schema:'aqlevon-runtime-metrics-v1',
    elapsed_ms:finiteNonNegativeOrNull(metrics.elapsed_ms,'elapsed_ms'),
    compute_device:String(metrics.compute_device||'unknown').slice(0,64),
    gpu_count:finiteNonNegativeOrNull(metrics.gpu_count,'gpu_count'),
    allocated_gpu_seconds:finiteNonNegativeOrNull(metrics.allocated_gpu_seconds,'allocated_gpu_seconds'),
    prompt_tokens:finiteNonNegativeOrNull(metrics.prompt_tokens,'prompt_tokens'),
    completion_tokens:finiteNonNegativeOrNull(metrics.completion_tokens,'completion_tokens'),
    total_tokens:finiteNonNegativeOrNull(metrics.total_tokens,'total_tokens'),
    cached_prompt_tokens:finiteNonNegativeOrNull(metrics.cached_prompt_tokens,'cached_prompt_tokens'),
    reasoning_tokens:finiteNonNegativeOrNull(metrics.reasoning_tokens,'reasoning_tokens'),
    cached_prompt_ratio:finiteNonNegativeOrNull(metrics.cached_prompt_ratio,'cached_prompt_ratio'),
    completion_tokens_per_second:finiteNonNegativeOrNull(metrics.completion_tokens_per_second,'completion_tokens_per_second'),
    completion_tokens_per_gpu_second:finiteNonNegativeOrNull(metrics.completion_tokens_per_gpu_second,'completion_tokens_per_gpu_second'),
    configured_gpu_power_watts:finiteNonNegativeOrNull(metrics.configured_gpu_power_watts,'configured_gpu_power_watts'),
    configured_gpu_hourly_usd:finiteNonNegativeOrNull(metrics.configured_gpu_hourly_usd,'configured_gpu_hourly_usd'),
    estimated_energy_wh:finiteNonNegativeOrNull(metrics.estimated_energy_wh,'estimated_energy_wh'),
    estimated_gpu_cost_usd:finiteNonNegativeOrNull(metrics.estimated_gpu_cost_usd,'estimated_gpu_cost_usd'),
  };
  if(normalized.cached_prompt_ratio!==null&&normalized.cached_prompt_ratio>1)throw new TypeError('invalid_cached_prompt_ratio');
  return normalized;
}

export function deriveRuntimeMetricProvenance(metrics){
  const m=normalizeRuntimeMetrics(metrics);
  return Object.freeze({
    elapsed_ms:'measured:performance.now_monotonic_wall_clock',
    token_usage:(m.prompt_tokens!==null||m.completion_tokens!==null)?'reported:openai_compatible_usage':null,
    allocated_gpu_seconds:m.allocated_gpu_seconds!==null?'estimated:elapsed_seconds_x_configured_gpu_count':null,
    estimated_energy_wh:m.estimated_energy_wh!==null?'estimated:allocated_gpu_seconds_x_configured_gpu_power_watts':null,
    estimated_gpu_cost_usd:m.estimated_gpu_cost_usd!==null?'estimated:allocated_gpu_seconds_x_configured_gpu_hourly_usd':null,
  });
}

export function buildRequestIdentity({modelRequest,harnessManifestSha256}){
  const harness=requireSha(harnessManifestSha256,'harness_manifest_sha256');
  const requestSha=sha256Canonical(modelRequest??{});
  return Object.freeze({request_sha256:requestSha,harness_manifest_sha256:harness});
}

export function buildRuntimeAttemptReceipt({
  attemptId=randomUUID(),
  taskId,
  candidateArtifactManifestSha256,
  requestIdentity,
  transportStatus,
  failureCode=null,
  runtimeMetrics,
  rawResultSha256=null,
}={}){
  const status=String(transportStatus||'');
  if(status!=='success'&&status!=='failure')throw new TypeError('invalid_transport_status');
  const requestSha=requireSha(requestIdentity?.request_sha256,'request_sha256');
  const harnessSha=requireSha(requestIdentity?.harness_manifest_sha256,'harness_manifest_sha256');
  const metrics=normalizeRuntimeMetrics(runtimeMetrics);
  const failure=status==='failure'?safeId(failureCode||'unspecified_failure','failure_code'):null;
  if(status==='success'&&failureCode!==null&&failureCode!==undefined&&String(failureCode).trim()!=='')throw new TypeError('success_cannot_have_failure_code');
  const rawHash=rawResultSha256===null||rawResultSha256===undefined?null:requireSha(rawResultSha256,'raw_result_sha256');
  const body={
    schema_version:'1',
    manifest_kind:RUNTIME_ATTEMPT_RECEIPT_KIND,
    attempt_id:safeId(attemptId,'attempt_id'),
    task_id:safeId(taskId,'task_id'),
    candidate_artifact_manifest_sha256:requireSha(candidateArtifactManifestSha256,'candidate_artifact_manifest_sha256'),
    request_harness_identity:{request_sha256:requestSha,harness_manifest_sha256:harnessSha},
    transport_outcome:{status,failure_code:failure},
    runtime_metrics:metrics,
    runtime_metric_provenance:deriveRuntimeMetricProvenance(metrics),
    raw_result_sha256:rawHash,
  };
  return Object.freeze({...body,receipt_sha256:sha256Canonical(body)});
}

export function validateRuntimeAttemptReceipt(receipt){
  const errors=[];
  if(!receipt||typeof receipt!=='object'||Array.isArray(receipt))return {valid:false,errors:['receipt_not_object']};
  const allowedTop=['schema_version','manifest_kind','attempt_id','task_id','candidate_artifact_manifest_sha256','request_harness_identity','transport_outcome','runtime_metrics','runtime_metric_provenance','raw_result_sha256','receipt_sha256'];
  if(Object.keys(receipt).some(key=>!allowedTop.includes(key)))errors.push('unknown_top_level_field');
  if(receipt.schema_version!=='1')errors.push('schema_version');
  if(receipt.manifest_kind!==RUNTIME_ATTEMPT_RECEIPT_KIND)errors.push('manifest_kind');
  try{safeId(receipt.attempt_id,'attempt_id')}catch{errors.push('attempt_id')}
  try{safeId(receipt.task_id,'task_id')}catch{errors.push('task_id')}
  if(!isSha256(receipt.candidate_artifact_manifest_sha256))errors.push('candidate_artifact_manifest_sha256');
  if(!isSha256(receipt?.request_harness_identity?.request_sha256))errors.push('request_sha256');
  if(!isSha256(receipt?.request_harness_identity?.harness_manifest_sha256))errors.push('harness_manifest_sha256');
  if(!['success','failure'].includes(receipt?.transport_outcome?.status))errors.push('transport_status');
  if(receipt?.transport_outcome?.status==='failure'&&!String(receipt?.transport_outcome?.failure_code||'').trim())errors.push('failure_code');
  if(receipt?.transport_outcome?.status==='success'&&receipt?.transport_outcome?.failure_code!==null)errors.push('success_failure_code');
  try{
    const normalized=normalizeRuntimeMetrics(receipt.runtime_metrics);
    if(canonicalJson(receipt.runtime_metric_provenance)!==canonicalJson(deriveRuntimeMetricProvenance(normalized)))errors.push('runtime_metric_provenance');
  }catch{errors.push('runtime_metrics')}
  if(receipt.raw_result_sha256!==null&&!isSha256(receipt.raw_result_sha256))errors.push('raw_result_sha256');
  if(!isSha256(receipt.receipt_sha256))errors.push('receipt_sha256');
  else{
    const {receipt_sha256,...body}=receipt;
    try{if(sha256Canonical(body)!==String(receipt_sha256).toLowerCase())errors.push('receipt_digest_mismatch')}
    catch{errors.push('receipt_digest_unverifiable')}
  }
  return {valid:errors.length===0,errors};
}

function validateEvaluationReceiptIdentity(receipt){
  if(!receipt||typeof receipt!=='object'||Array.isArray(receipt))return false;
  return receipt.manifest_kind===EVALUATION_DECISION_RECEIPT_KIND
    &&isSha256(receipt.receipt_sha256)
    &&isSha256(receipt.candidate_artifact_manifest_sha256)
    &&['INVALID','REJECTED','PROMOTION_ELIGIBLE'].includes(receipt.final_status);
}

function validateObjectiveVerifierApproval(receipt){
  if(!receipt||typeof receipt!=='object'||Array.isArray(receipt))return false;
  return isSha256(receipt.receipt_sha256)
    &&isSha256(receipt.attempt_receipt_sha256)
    &&isSha256(receipt.manager_approval_receipt_sha256)
    &&['VERIFIED_SUCCESS','VERIFIED_FAILURE','INVALID'].includes(receipt.verification_status);
}

export function resolveAttemptVerification(attemptReceipt,{
  evaluationDecisionReceipts=[],
  objectiveVerifierApprovals=[],
  verificationJoins=[],
}={}){
  const attemptValidation=validateRuntimeAttemptReceipt(attemptReceipt);
  if(!attemptValidation.valid||attemptReceipt.transport_outcome.status!=='success')return Object.freeze({verified:false,source:null,receipt_sha256:null});
  const attemptHash=String(attemptReceipt.receipt_sha256).toLowerCase();
  const evalByHash=new Map();
  for(const receipt of Array.isArray(evaluationDecisionReceipts)?evaluationDecisionReceipts:[]){
    if(validateEvaluationReceiptIdentity(receipt))evalByHash.set(String(receipt.receipt_sha256).toLowerCase(),receipt);
  }
  const objectiveByHash=new Map();
  for(const receipt of Array.isArray(objectiveVerifierApprovals)?objectiveVerifierApprovals:[]){
    if(validateObjectiveVerifierApproval(receipt))objectiveByHash.set(String(receipt.receipt_sha256).toLowerCase(),receipt);
  }
  for(const join of Array.isArray(verificationJoins)?verificationJoins:[]){
    if(!isSha256(join?.attempt_receipt_sha256)||!isSha256(join?.verification_receipt_sha256))continue;
    if(String(join.attempt_receipt_sha256).toLowerCase()!==attemptHash)continue;
    const verificationHash=String(join.verification_receipt_sha256).toLowerCase();
    const evalReceipt=evalByHash.get(verificationHash);
    if(evalReceipt){
      if(evalReceipt.final_status!=='PROMOTION_ELIGIBLE')continue;
      if(String(evalReceipt.candidate_artifact_manifest_sha256).toLowerCase()!==String(attemptReceipt.candidate_artifact_manifest_sha256).toLowerCase())continue;
      return Object.freeze({verified:true,source:'evaluation_decision',receipt_sha256:verificationHash});
    }
    const objectiveReceipt=objectiveByHash.get(verificationHash);
    if(objectiveReceipt){
      if(objectiveReceipt.verification_status!=='VERIFIED_SUCCESS')continue;
      if(String(objectiveReceipt.attempt_receipt_sha256).toLowerCase()!==attemptHash)continue;
      return Object.freeze({verified:true,source:'objective_verifier',receipt_sha256:verificationHash});
    }
  }
  return Object.freeze({verified:false,source:null,receipt_sha256:null});
}

export function isAttemptVerifiedSuccess(attemptReceipt,options={}){
  return resolveAttemptVerification(attemptReceipt,options).verified;
}
