import { createHash, randomUUID } from 'crypto';
import { EFFECT_CAPABILITIES } from './constants.js';
import { stableJson } from './security.js';

const sha256=v=>createHash('sha256').update(String(v)).digest('hex');
const ACTIVE='ACTIVE';
const capSet=new Set(EFFECT_CAPABILITIES);

function canonical(value){return JSON.parse(stableJson(value))}
function nowMs(now){return new Date(now||Date.now()).getTime()}

export function canonicalResource(raw={}){
  const provider=String(raw.provider||'').trim();
  const tenant=String(raw.tenant||raw.account||'').trim();
  const project=String(raw.project||'').trim();
  const environment=String(raw.environment||'').trim();
  const namespace=String(raw.namespace||'').trim();
  const resource_id=String(raw.resource_id||raw.id||'').trim();
  if(!provider||!tenant||!environment||!resource_id)throw new Error('resource identity must bind provider, tenant, environment, and immutable resource_id');
  return Object.freeze({provider,tenant,project,environment,namespace,resource_id});
}

export function createActionIntent({task_id,contract_id,semantic_action,resource,parameters={},capabilities=[],idempotency_identity=null}){
  const caps=[...new Set(capabilities.map(String))].sort();
  for(const cap of caps)if(!capSet.has(cap))throw new Error(`unknown capability ${cap}`);
  const exactResource=canonicalResource(resource);
  const exactParameters=canonical(parameters);
  return Object.freeze({
    id:randomUUID(),task_id:String(task_id),contract_id:String(contract_id),
    semantic_action:String(semantic_action),canonical_resource:exactResource,
    canonical_parameters:exactParameters,parameter_digest:sha256(stableJson(exactParameters)),
    effective_capabilities:caps,idempotency_identity:idempotency_identity?String(idempotency_identity):null,
    auth_state:'PROPOSED',created_at:new Date().toISOString(),
  });
}

export function selectApplicableConstraints(constraints=[],resource,capabilities=[],now=Date.now()){
  const t=nowMs(now);const caps=new Set(capabilities);
  return constraints.filter(c=>{
    if(c?.status!==ACTIVE)return false;
    if(c.valid_from&&new Date(c.valid_from).getTime()>t)return false;
    if(c.expires_at&&new Date(c.expires_at).getTime()<=t)return false;
    const a=c.applicability||{};
    if(a.provider&&a.provider!==resource.provider)return false;
    if(a.tenant&&a.tenant!==resource.tenant)return false;
    if(a.project&&a.project!==resource.project)return false;
    if(a.environment&&a.environment!==resource.environment)return false;
    if(a.resource_ids&&Array.isArray(a.resource_ids)&&!a.resource_ids.includes(resource.resource_id))return false;
    if(a.capabilities&&Array.isArray(a.capabilities)&&!a.capabilities.some(x=>caps.has(x)))return false;
    return true;
  }).sort((a,b)=>String(a.constraint_id).localeCompare(String(b.constraint_id))||Number(a.version)-Number(b.version));
}

export function evaluateConstraints(constraints=[],intent){
  let confirmationRequired=false;const reasons=[];
  for(const c of constraints){
    const r=c.rule_spec||{};
    const effect=String(r.effect||r.mode||'REQUIRE').toUpperCase();
    if(effect==='DENY')reasons.push(`constraint ${c.constraint_id}@${c.version} denies this action`);
    if(effect==='REQUIRE_CONFIRMATION')confirmationRequired=true;
    if(r.forbid_capabilities&&intent.effective_capabilities.some(x=>r.forbid_capabilities.includes(x)))reasons.push(`constraint ${c.constraint_id}@${c.version} forbids capability`);
  }
  return {allowed:reasons.length===0,confirmation_required:confirmationRequired,reasons};
}

export function constraintSetBinding(constraints=[]){
  const refs=constraints.map(c=>({constraint_id:String(c.constraint_id),version:Number(c.version),rule_hash:String(c.rule_hash||'')}));
  return {refs,constraint_set_digest:sha256(stableJson(refs))};
}

export function issuePermit({principal,taskContract,intent,toolSpec,constraints=[],confirmation=null,now=Date.now(),expires_at=null}){
  const t=nowMs(now);
  if(!principal||principal.status!=='ACTIVE')throw new Error('principal binding is not active');
  if(principal.expires_at&&new Date(principal.expires_at).getTime()<=t)throw new Error('principal binding expired');
  if(String(intent.contract_id)!==String(taskContract.contract_id||taskContract.id))throw new Error('intent is bound to a different TaskContract');
  if(!toolSpec||!['ACTIVE','APPROVED'].includes(toolSpec.lifecycle))throw new Error('ToolSpec is not executable');
  const missing=intent.effective_capabilities.filter(c=>!toolSpec.capabilities.includes(c));
  if(missing.length)throw new Error(`ToolSpec does not cover capabilities: ${missing.join(', ')}`);
  const applicable=selectApplicableConstraints(constraints,intent.canonical_resource,intent.effective_capabilities,now);
  const evaluation=evaluateConstraints(applicable,intent);
  if(!evaluation.allowed)throw new Error(evaluation.reasons.join('; '));
  if(evaluation.confirmation_required&&!confirmation)throw new Error('confirmation required by current DurableConstraint');
  const {refs,constraint_set_digest}=constraintSetBinding(applicable);
  const binding={
    principal_binding_id:String(principal.id),task_id:String(intent.task_id),contract_id:String(intent.contract_id),
    action_intent_id:String(intent.id),semantic_action:intent.semantic_action,
    resource:intent.canonical_resource,parameters:intent.canonical_parameters,parameter_digest:intent.parameter_digest,
    capabilities:intent.effective_capabilities,tool_id:toolSpec.tool_id,tool_version:toolSpec.version,tool_spec_digest:toolSpec.spec_digest,
    constraint_refs:refs,constraint_set_digest,confirmation_id:confirmation?.id||null,
  };
  return Object.freeze({
    id:randomUUID(),...binding,exact_binding_digest:sha256(stableJson(binding)),status:'ACTIVE',
    valid_from:new Date(t).toISOString(),expires_at:expires_at?new Date(expires_at).toISOString():null,created_at:new Date(t).toISOString(),
  });
}

export function preDispatchCheck({permit,principal,taskContract,intent,toolSpec,constraints=[],now=Date.now()}){
  const reasons=[];const t=nowMs(now);
  if(!permit||permit.status!=='ACTIVE')reasons.push('Permit is not ACTIVE');
  if(permit?.expires_at&&new Date(permit.expires_at).getTime()<=t)reasons.push('Permit expired');
  if(!principal||principal.status!=='ACTIVE')reasons.push('PrincipalBinding is not ACTIVE');
  if(principal?.expires_at&&new Date(principal.expires_at).getTime()<=t)reasons.push('PrincipalBinding expired');
  if(String(permit?.contract_id)!==String(taskContract?.contract_id||taskContract?.id))reasons.push('TaskContract binding changed');
  if(String(permit?.action_intent_id)!==String(intent?.id))reasons.push('ActionIntent identity mismatch');
  if(stableJson(permit?.resource)!==stableJson(intent?.canonical_resource))reasons.push('resource changed after authorization');
  if(stableJson(permit?.parameters)!==stableJson(intent?.canonical_parameters)||permit?.parameter_digest!==intent?.parameter_digest)reasons.push('consequential parameters changed after authorization');
  if(!toolSpec||toolSpec.tool_id!==permit?.tool_id||toolSpec.version!==permit?.tool_version||toolSpec.spec_digest!==permit?.tool_spec_digest||!['ACTIVE','APPROVED'].includes(toolSpec.lifecycle))reasons.push('pinned ToolSpec is no longer the authorized executable contract');
  const applicable=selectApplicableConstraints(constraints,intent.canonical_resource,intent.effective_capabilities,now);
  const current=constraintSetBinding(applicable);
  if(current.constraint_set_digest!==permit?.constraint_set_digest)reasons.push('applicable DurableConstraint set changed');
  const evalNow=evaluateConstraints(applicable,intent);if(!evalNow.allowed)reasons.push(...evalNow.reasons);
  return {allowed:reasons.length===0,reasons,current_constraint_set_digest:current.constraint_set_digest};
}
