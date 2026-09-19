import {createHash} from 'node:crypto';

export const P2_HASH_PROFILE='AQLEVON_CANONICAL_JSON_SHA256_V1';
export const RUNTIME_ATTEMPT_RECEIPT_KIND='AQLEVON_RUNTIME_ATTEMPT_RECEIPT_V1';
export const EVALUATION_DECISION_RECEIPT_KIND='AQLEVON_EVALUATION_DECISION_RECEIPT_V1';
export const RUNTIME_ATTEMPT_POPULATION_KIND='AQLEVON_RUNTIME_ATTEMPT_POPULATION_V1';
const SHA256_RE=/^[0-9a-f]{64}$/;
const CANONICAL_DECIMAL_RE=/^-?(?:0|[1-9]\d*)(?:\.\d*[1-9])?$/;
const TOP_LEVEL_KEYS=new Set([
  'schema_version','receipt_kind','hash_profile','attempt_id','task_id','candidate_artifact_manifest_sha256',
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
function normalizeString(value){return String(value).normalize('NFKC').replace(/\r\n?/g,'\n')}

function normalizeDecimalString(raw){
  let s=String(raw).trim().toLowerCase();
  let sign='';
  if(s.startsWith('+'))s=s.slice(1);
  else if(s.startsWith('-')){sign='-';s=s.slice(1)}
  let [intPart='0',fracPart='']=s.split('.');
  intPart=intPart.replace(/^0+(?=\d)/,'')||'0';
  fracPart=fracPart.replace(/0+$/,'');
  const zero=intPart==='0'&&!fracPart;
  return `${zero?'':sign}${intPart}${fracPart?`.${fracPart}`:''}`;
}

export function canonicalDecimalString(value){
  const n=Number(value);
  if(!Number.isFinite(n))throw new TypeError('non_finite_number');
  if(Object.is(n,-0)||n===0)return '0';
  if(Number.isInteger(n)){
    if(!Number.isSafeInteger(n))throw new TypeError('unsafe_integer');
    return String(n);
  }
  let s=n.toString().toLowerCase();
  if(!s.includes('e'))return normalizeDecimalString(s);
  const sign=s.startsWith('-')?'-':'';
  if(sign)s=s.slice(1);
  const [coefficient,expRaw]=s.split('e');
  const exponent=Number(expRaw);
  const [whole,frac='']=coefficient.split('.');
  const digits=(whole+frac).replace(/^0+/,'')||'0';
  const decimalPos=whole.length+exponent;
  let expanded;
  if(decimalPos<=0)expanded=`0.${'0'.repeat(-decimalPos)}${digits}`;
  else if(decimalPos>=digits.length)expanded=digits+'0'.repeat(decimalPos-digits.length);
  else expanded=`${digits.slice(0,decimalPos)}.${digits.slice(decimalPos)}`;
  return normalizeDecimalString(sign+expanded);
}

function canonicalProfileValue(value){
  if(value===null||typeof value==='boolean')return value;
  if(typeof value==='string')return normalizeString(value);
  if(typeof value==='number'){
    if(!Number.isFinite(value))throw new TypeError('non_finite_number');
    if(Number.isInteger(value)){
      if(!Number.isSafeInteger(value))throw new TypeError('unsafe_integer');
      return Object.is(value,-0)?0:value;
    }
    return canonicalDecimalString(value);
  }
  if(Array.isArray(value))return value.map(canonicalProfileValue);
  if(value&&typeof value==='object'){
    const out={};
    for(const key of Object.keys(value).sort()){
      if(!/^[\x00-\x7f]+$/.test(key))throw new TypeError('non_ascii_object_key');
      if(value[key]===undefined)throw new TypeError('undefined_json_value');
      out[key]=canonicalProfileValue(value[key]);
    }
    return out;
  }
  throw new TypeError('unsupported_json_value');
}

export function canonicalJson(value){return JSON.stringify(canonicalProfileValue(value))}
export function sha256Text(value){return createHash('sha256').update(String(value),'utf8').digest('hex')}
export function sha256Canonical(value){return sha256Text(canonicalJson(value))}
export function hashRuntimeResult(value){return sha256Canonical(value)}

function containsDirectFloat(value){
  if(typeof value==='number')return !Number.isInteger(value);
  if(Array.isArray(value))return value.some(containsDirectFloat);
  if(value&&typeof value==='object')return Object.values(value).some(containsDirectFloat);
  return false;
}

export function verifyP2SelfDigest(receipt,{digestField='receipt_sha256'}={}){
  if(!receipt||typeof receipt!=='object'||Array.isArray(receipt))return false;
  if(receipt.hash_profile!==P2_HASH_PROFILE)return false;
  if(!isSha256Hex(receipt[digestField]))return false;
  if(containsDirectFloat(receipt))return false;
  const body={...receipt};delete body[digestField];
  try{return sha256Canonical(body)===receipt[digestField]}catch{return false}
}

export function validateRuntimeReceiptIdentityConfig({candidateArtifactManifestSha256='',harnessManifestSha256=''}={}){
  const candidate=String(candidateArtifactManifestSha256||'').trim().toLowerCase();
  const harness=String(harnessManifestSha256||'').trim().toLowerCase();
  const requested=Boolean(candidate||harness);
  const ok=!requested||(isSha256Hex(candidate)&&isSha256Hex(harness));
  return Object.freeze({
    ok,requested,configured:requested&&ok,
    candidate_artifact_manifest_sha256:candidate||null,
    harness_manifest_sha256:harness||null,
    reason:ok?null:'candidate_and_harness_sha256_required',
  });
}

function exactKeys(value,allowed){
  if(!value||typeof value!=='object'||Array.isArray(value))return false;
  const keys=Object.keys(value);
  return keys.length===allowed.size&&keys.every(key=>allowed.has(key));
}
function nonemptyId(value){return typeof value==='string'&&value.trim().length>0&&value.trim().length<=256}
function isCanonicalNonNegativeNumeric(value){
  if(value===null)return true;
  if(typeof value==='number')return Number.isSafeInteger(value)&&value>=0;
  if(typeof value==='string'&&CANONICAL_DECIMAL_RE.test(value)){
    const n=Number(value);return Number.isFinite(n)&&n>=0&&canonicalDecimalString(n)===value;
  }
  return false;
}
function isCanonicalNonNegativeInteger(value){return value===null||(Number.isSafeInteger(value)&&value>=0)}

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
    if(!isCanonicalNonNegativeNumeric(metrics[key]))reasons.push(`runtime_metric_${key}`);
  }
  if(!isCanonicalNonNegativeInteger(metrics.gpu_count))reasons.push('runtime_metric_gpu_count');
  const cachedRatio=metrics.cached_prompt_ratio===null?null:Number(metrics.cached_prompt_ratio);
  if(cachedRatio!==null&&cachedRatio>1)reasons.push('cached_prompt_ratio_range');
}

export function buildRuntimeAttemptReceipt({
  attemptId,taskId,candidateArtifactManifestSha256,requestIdentity,transportOutcome,
  runtimeMetrics,measurementProvenance=buildRuntimeMeasurementProvenance(runtimeMetrics),rawResultSha256=null,
}={}){
  const draft=canonicalProfileValue({
    schema_version:1,
    receipt_kind:RUNTIME_ATTEMPT_RECEIPT_KIND,
    hash_profile:P2_HASH_PROFILE,
    attempt_id:String(attemptId||''),
    task_id:String(taskId||''),
    candidate_artifact_manifest_sha256:String(candidateArtifactManifestSha256||'').toLowerCase(),
    request_identity:requestIdentity,
    transport_outcome:transportOutcome,
    runtime_metrics:runtimeMetrics,
    measurement_provenance:measurementProvenance,
    raw_result_sha256:rawResultSha256===null?null:String(rawResultSha256).toLowerCase(),
  });
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
  if(receipt?.hash_profile!==P2_HASH_PROFILE)reasons.push('hash_profile');
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
  if(containsDirectFloat(receipt))reasons.push('noncanonical_float_representation');
  if(reasons.length===0&&!verifyP2SelfDigest(receipt))reasons.push('receipt_self_hash_mismatch');
  return Object.freeze({ok:reasons.length===0,reasons:Object.freeze(reasons)});
}

export function buildRuntimePopulationScope(attemptReceipts=[]){
  const attempts=Array.isArray(attemptReceipts)?attemptReceipts:[];
  const ids=attempts.map(r=>String(r?.receipt_sha256||'').toLowerCase()).filter(isSha256Hex).sort();
  const candidates=[...new Set(attempts.map(r=>String(r?.candidate_artifact_manifest_sha256||'').toLowerCase()).filter(isSha256Hex))].sort();
  const root={
    hash_profile:P2_HASH_PROFILE,
    population_kind:RUNTIME_ATTEMPT_POPULATION_KIND,
    attempt_receipt_sha256s:ids,
    candidate_artifact_manifest_sha256s:candidates,
  };
  return Object.freeze({
    hash_profile:P2_HASH_PROFILE,
    population_kind:RUNTIME_ATTEMPT_POPULATION_KIND,
    attempt_count:attempts.length,
    candidate_count:candidates.length,
    attempt_set_sha256:ids.length===attempts.length?sha256Canonical(root):null,
  });
}

export function buildApprovedTruthAuthority(truth={}){
  const reasons=[];
  const allowedKeys=new Set(['approvedEvaluationReceipts','approvedObjectiveVerifierReceipts']);
  if(!truth||typeof truth!=='object'||Array.isArray(truth)){
    return {ok:false,reasons:['truth_authority_type'],evalByCandidate:new Map(),objectiveByAttempt:new Map(),approvedEvaluationCount:0,approvedObjectiveCount:0};
  }
  if(Object.keys(truth).some(key=>!allowedKeys.has(key)))reasons.push('truth_authority_schema');
  const evaluationReceipts=truth.approvedEvaluationReceipts??[];
  const objectiveReceipts=truth.approvedObjectiveVerifierReceipts??[];
  if(!Array.isArray(evaluationReceipts))reasons.push('approved_evaluation_receipts_type');
  if(!Array.isArray(objectiveReceipts))reasons.push('approved_objective_receipts_type');
  const evalByCandidate=new Map();
  const objectiveByAttempt=new Map();
  const identityProjection=new Map();
  let approvedEvaluationCount=0,approvedObjectiveCount=0;
  function bindIdentity(id,projection){
    const prior=identityProjection.get(id);
    if(prior!==undefined&&prior!==projection){reasons.push('approved_truth_identity_conflict');return false}
    identityProjection.set(id,projection);return true;
  }
  for(const receipt of Array.isArray(evaluationReceipts)?evaluationReceipts:[]){
    const id=String(receipt?.receipt_sha256||'').toLowerCase();
    const candidate=String(receipt?.candidate_artifact_manifest_sha256||'').toLowerCase();
    const status=receipt?.final_status;
    if(receipt?.schema_version!==1||receipt?.receipt_kind!==EVALUATION_DECISION_RECEIPT_KIND||receipt?.hash_profile!==P2_HASH_PROFILE||!verifyP2SelfDigest(receipt)||!isSha256Hex(candidate)||!['INVALID','REJECTED','PROMOTION_ELIGIBLE'].includes(status)){
      reasons.push('approved_evaluation_receipt_invalid');continue;
    }
    if(!bindIdentity(id,`evaluation:${candidate}:${status}`))continue;
    const list=evalByCandidate.get(candidate)||[];
    list.push({receipt_sha256:id,final_status:status});
    evalByCandidate.set(candidate,list);
    approvedEvaluationCount++;
  }
  for(const receipt of Array.isArray(objectiveReceipts)?objectiveReceipts:[]){
    const id=String(receipt?.receipt_sha256||'').toLowerCase();
    const attempt=String(receipt?.attempt_receipt_sha256||'').toLowerCase();
    const candidate=String(receipt?.candidate_artifact_manifest_sha256||'').toLowerCase();
    const verdict=receipt?.verdict;
    if(receipt?.schema_version!==1||receipt?.hash_profile!==P2_HASH_PROFILE||!nonemptyId(receipt?.receipt_kind)||!verifyP2SelfDigest(receipt)||!isSha256Hex(attempt)||!isSha256Hex(candidate)||!['PASS','FAIL','INVALID'].includes(verdict)){
      reasons.push('approved_objective_receipt_invalid');continue;
    }
    if(!bindIdentity(id,`objective:${attempt}:${candidate}:${verdict}`))continue;
    const list=objectiveByAttempt.get(attempt)||[];
    list.push({receipt_sha256:id,candidate_artifact_manifest_sha256:candidate,verdict});
    objectiveByAttempt.set(attempt,list);
    approvedObjectiveCount++;
  }
  return {ok:reasons.length===0,reasons,evalByCandidate,objectiveByAttempt,approvedEvaluationCount,approvedObjectiveCount};
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
    return {verified:false,source:'evaluation_decision',reason:'candidate_receipt_not_attempt_binding',conflict:false};
  }
  return {verified:false,source:null,reason:'no_approved_attempt_verifier',conflict:false};
}
