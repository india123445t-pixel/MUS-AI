import {createHash} from 'node:crypto';

export const RUNTIME_ATTEMPT_RECEIPT_KIND='AQLEVON_RUNTIME_ATTEMPT_RECEIPT_V1';
export const EVALUATION_DECISION_RECEIPT_KIND='AQLEVON_EVALUATION_DECISION_RECEIPT_V1';
const SHA256_RE=/^[0-9a-f]{64}$/i;
const TOP_LEVEL_KEYS=new Set([
  'schema_version','receipt_kind','attempt_id','task_id','candidate_artifact_manifest_sha256',
  'request_identity','transport_outcome','runtime_metrics','measurement_provenance',
  'raw_result_sha256','receipt_sha256'
]);
const REQUEST_IDENTITY_KEYS=new Set(['request_sha256','harness_manifest_sha256']);
const TRANSPORT_KEYS=new Set(['status','failure_code']);
const PROVENANCE_KEYS=new Set([
  'elapsed_ms_source','token_usage_source','gpu_allocation_source','energy_estimate_source','cost_estimate_source'
]);
const RUNTIME_METRIC_KEYS=new Set([
  'schema','elapsed_ms','compute_device','gpu_count','allocated_gpu_seconds','prompt_tokens','completion_tokens',
  'total_tokens','cached_prompt_tokens','reasoning_tokens','cached_prompt_ratio','completion_tokens_per_second',
  'completion_tokens_per_gpu_second','configured_gpu_power_watts','configured_gpu_hourly_usd',
  'estimated_energy_wh','estimated_gpu_cost_usd'
]);

export function isSha256Hex(value){return typeof value==='string'&&SHA256_RE.test(value)}

function normalizedJson(value){
  if(value===null||typeof value==='string'||typeof value==='boolean')return value;
  if(typeof value==='number'){
    if(!Number.isFinite(value))throw new TypeError('non_finite_number');
    return value;
  }
  if(Array.isArray(value))return value.map(normalizedJson);
  if(typeof value==='object'){
    const out={};
    for(const key of Object.keys(value).sort()){
      if(value[key]===undefined)continue;
      out[key]=normalizedJson(value[key]);
    }
    return out;
  }
  throw new TypeError('unsupported_json_value');
}

export function canonicalJson(value){return JSON.stringify(normalizedJson(value))}
export function sha256Text(value){return createHash('sha256').update(String(value),'utf8').digest('hex')}
export function sha256Canonical(value){return sha256Text(canonicalJson(value))}
export function hashRuntimeResult(value){return sha256Canonical(value)}

function exactKeys(value,allowed){
  if(!value||typeof value!=='object'||Array.isArray(value))return false;
  const keys=Object.keys(value);
  return keys.length===allowed.size&&keys.every(key=>allowed.has(key));
}
function nonemptyId(value){return typeof value==='string'&&value.trim().length>0&&value.trim().length<=256}
function finiteNonNegativeOrNull(value){return value===null||(Number.isFinite(value)&&value>=0)}
function integerNonNegativeOrNull(value){return value===null||(Number.isInteger(value)&&value>=0)}

export function buildRequestIdentity({request,harnessManifestSha256}={}){
  if(!isSha256Hex(harnessManifestSha256))throw new TypeError('invalid_harness_manifest_sha256');
  return Object.freeze({
    request_sha256:sha256Canonical(request??{}),
    harness_manifest_sha256:String(harnessManifestSha256).toLowerCase(),
  });
}

export function buildRuntimeMeasurementProvenance(runtimeMetrics={}){
  const tokenSeen=[runtimeMetrics?.prompt_tokens,runtimeMetrics?.completion_tokens,runtimeMetrics?.total_tokens].some(v=>v!==null&&v!==undefined);
  return Object.freeze({
    elapsed_ms_source:runtimeMetrics?.elapsed_ms!==null&&runtimeMetrics?.elapsed_ms!==undefined?'worker_monotonic_clock':'unavailable',
    token_usage_source:tokenSeen?'openai_compatible_backend_usage':'unavailable',
    gpu_allocation_source:runtimeMetrics?.gpu_count!==null&&runtimeMetrics?.gpu_count!==undefined?'operator_configured_gpu_count':'unavailable',
    energy_estimate_source:runtimeMetrics?.estimated_energy_wh!==null&&runtimeMetrics?.estimated_energy_wh!==undefined?'configured_power_x_allocated_gpu_seconds':'unavailable',
    cost_estimate_source:runtimeMetrics?.estimated_gpu_cost_usd!==null&&runtimeMetrics?.estimated_gpu_cost_usd!==undefined?'configured_rate_x_allocated_gpu_seconds':'unavailable',
  });
}

function validateRuntimeMetrics(metrics,reasons){
  if(!exactKeys(metrics,RUNTIME_METRIC_KEYS)){reasons.push('runtime_metrics_schema');return}
  if(metrics.schema!=='aqlevon-runtime-metrics-v1')reasons.push('runtime_metrics_kind');
  if(typeof metrics.compute_device!=='string'||metrics.compute_device.length>64)reasons.push('compute_device');
  for(const key of ['elapsed_ms','allocated_gpu_seconds','prompt_tokens','completion_tokens','total_tokens','cached_prompt_tokens','reasoning_tokens','cached_prompt_ratio','completion_tokens_per_second','completion_tokens_per_gpu_second','configured_gpu_power_watts','configured_gpu_hourly_usd','estimated_energy_wh','estimated_gpu_cost_usd']){
    if(!finiteNonNegativeOrNull(metrics[key]))reasons.push(`runtime_metric_${key}`);
  }
  if(!integerNonNegativeOrNull(metrics.gpu_count))reasons.push('runtime_metric_gpu_count');
  if(metrics.cached_prompt_ratio!==null&&metrics.cached_prompt_ratio>1)reasons.push('cached_prompt_ratio_range');
}

export function buildRuntimeAttemptReceipt({
  attemptId,taskId,candidateArtifactManifestSha256,requestIdentity,transportOutcome,
  runtimeMetrics,measurementProvenance=buildRuntimeMeasurementProvenance(runtimeMetrics),rawResultSha256=null,
}={}){
  const draft={
    schema_version:1,
    receipt_kind:RUNTIME_ATTEMPT_RECEIPT_KIND,
    attempt_id:String(attemptId||''),
    task_id:String(taskId||''),
    candidate_artifact_manifest_sha256:String(candidateArtifactManifestSha256||'').toLowerCase(),
    request_identity:normalizedJson(requestIdentity),
    transport_outcome:normalizedJson(transportOutcome),
    runtime_metrics:normalizedJson(runtimeMetrics),
    measurement_provenance:normalizedJson(measurementProvenance),
    raw_result_sha256:rawResultSha256===null?null:String(rawResultSha256).toLowerCase(),
  };
  const receipt={...draft,receipt_sha256:sha256Canonical(draft)};
  const check=verifyRuntimeAttemptReceipt(receipt);
  if(!check.ok)throw new TypeError(`invalid_runtime_attempt_receipt:${check.reasons.join(',')}`);
  return Object.freeze(receipt);
}

export function verifyRuntimeAttemptReceipt(receipt){
  const reasons=[];
  if(!exactKeys(receipt,TOP_LEVEL_KEYS))reasons.push('top_level_schema');
  if(receipt?.schema_version!==1)reasons.push('schema_version');
  if(receipt?.receipt_kind!==RUNTIME_ATTEMPT_RECEIPT_KIND)reasons.push('receipt_kind');
  if(!nonemptyId(receipt?.attempt_id))reasons.push('attempt_id');
  if(!nonemptyId(receipt?.task_id))reasons.push('task_id');
  if(!isSha256Hex(receipt?.candidate_artifact_manifest_sha256))reasons.push('candidate_artifact_manifest_sha256');
  if(!exactKeys(receipt?.request_identity,REQUEST_IDENTITY_KEYS))reasons.push('request_identity_schema');
  else{
    if(!isSha256Hex(receipt.request_identity.request_sha256))reasons.push('request_sha256');
    if(!isSha256Hex(receipt.request_identity.harness_manifest_sha256))reasons.push('harness_manifest_sha256');
  }
  if(!exactKeys(receipt?.transport_outcome,TRANSPORT_KEYS))reasons.push('transport_outcome_schema');
  else{
    if(!['success','failed'].includes(receipt.transport_outcome.status))reasons.push('transport_status');
    const failure=receipt.transport_outcome.failure_code;
    if(receipt.transport_outcome.status==='success'&&failure!==null)reasons.push('success_failure_code');
    if(receipt.transport_outcome.status==='failed'&&(!nonemptyId(failure)||failure.length>128))reasons.push('failed_failure_code');
  }
  validateRuntimeMetrics(receipt?.runtime_metrics,reasons);
  if(!exactKeys(receipt?.measurement_provenance,PROVENANCE_KEYS))reasons.push('measurement_provenance_schema');
  else for(const key of PROVENANCE_KEYS){if(!nonemptyId(receipt.measurement_provenance[key]))reasons.push(`measurement_provenance_${key}`)}
  if(receipt?.raw_result_sha256!==null&&!isSha256Hex(receipt?.raw_result_sha256))reasons.push('raw_result_sha256');
  if(!isSha256Hex(receipt?.receipt_sha256))reasons.push('receipt_sha256');
  if(reasons.length===0){
    const {receipt_sha256,...draft}=receipt;
    if(sha256Canonical(draft)!==receipt_sha256.toLowerCase())reasons.push('receipt_self_hash_mismatch');
  }
  return Object.freeze({ok:reasons.length===0,reasons:Object.freeze(reasons)});
}

export function buildApprovedTruthAuthority({evaluationReceipts=[],objectiveVerifierReceipts=[],approvedTruthReceiptSha256s=[]}={}){
  const reasons=[];
  if(!Array.isArray(approvedTruthReceiptSha256s))reasons.push('approved_truth_ids_type');
  const approved=new Set();
  for(const id of Array.isArray(approvedTruthReceiptSha256s)?approvedTruthReceiptSha256s:[]){
    if(!isSha256Hex(id))reasons.push('approved_truth_id_invalid');
    else approved.add(id.toLowerCase());
  }
  const evalByCandidate=new Map();
  const objectiveByAttempt=new Map();
  let ignoredUnapproved=0;
  for(const receipt of Array.isArray(evaluationReceipts)?evaluationReceipts:[]){
    const id=String(receipt?.receipt_sha256||'').toLowerCase();
    if(!approved.has(id)){ignoredUnapproved++;continue}
    if((receipt?.receipt_kind??receipt?.manifest_kind)!==EVALUATION_DECISION_RECEIPT_KIND||!isSha256Hex(id)||!isSha256Hex(receipt?.candidate_artifact_manifest_sha256)||!['INVALID','REJECTED','PROMOTION_ELIGIBLE'].includes(receipt?.final_status)){
      reasons.push('approved_evaluation_receipt_invalid');continue;
    }
    const key=receipt.candidate_artifact_manifest_sha256.toLowerCase();
    const list=evalByCandidate.get(key)||[];list.push({receipt_sha256:id,final_status:receipt.final_status});evalByCandidate.set(key,list);
  }
  for(const receipt of Array.isArray(objectiveVerifierReceipts)?objectiveVerifierReceipts:[]){
    const id=String(receipt?.receipt_sha256||'').toLowerCase();
    if(!approved.has(id)){ignoredUnapproved++;continue}
    if(!isSha256Hex(id)||!isSha256Hex(receipt?.attempt_receipt_sha256)||!isSha256Hex(receipt?.candidate_artifact_manifest_sha256)||!['PASS','FAIL','INVALID'].includes(receipt?.verdict)){
      reasons.push('approved_objective_receipt_invalid');continue;
    }
    const key=receipt.attempt_receipt_sha256.toLowerCase();
    const list=objectiveByAttempt.get(key)||[];list.push({receipt_sha256:id,candidate_artifact_manifest_sha256:receipt.candidate_artifact_manifest_sha256.toLowerCase(),verdict:receipt.verdict});objectiveByAttempt.set(key,list);
  }
  return {ok:reasons.length===0,reasons,approved,evalByCandidate,objectiveByAttempt,ignoredUnapproved};
}

export function resolveAttemptVerification(attemptReceipt,authority){
  if(!authority?.ok)return {verified:false,source:null,reason:'authority_invalid',conflict:false};
  if(attemptReceipt?.transport_outcome?.status!=='success')return {verified:false,source:null,reason:'transport_failed',conflict:false};
  const attemptId=String(attemptReceipt.receipt_sha256).toLowerCase();
  const candidate=String(attemptReceipt.candidate_artifact_manifest_sha256).toLowerCase();
  const objective=(authority.objectiveByAttempt.get(attemptId)||[]).filter(r=>r.candidate_artifact_manifest_sha256===candidate);
  if(objective.length){
    const verdicts=new Set(objective.map(r=>r.verdict));
    if(verdicts.size>1)return {verified:false,source:'objective_verifier',reason:'truth_conflict',conflict:true};
    const verdict=[...verdicts][0];
    return {verified:verdict==='PASS',source:'objective_verifier',reason:verdict,conflict:false};
  }
  const evaluations=authority.evalByCandidate.get(candidate)||[];
  if(evaluations.length){
    const statuses=new Set(evaluations.map(r=>r.final_status));
    if(statuses.size>1)return {verified:false,source:'evaluation_decision',reason:'truth_conflict',conflict:true};
    const status=[...statuses][0];
    return {verified:status==='PROMOTION_ELIGIBLE',source:'evaluation_decision',reason:status,conflict:false};
  }
  return {verified:false,source:null,reason:'no_approved_truth_receipt',conflict:false};
}
