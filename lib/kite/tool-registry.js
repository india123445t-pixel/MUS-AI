import { EFFECT_CAPABILITIES } from './constants.js';
import { stableJson } from './security.js';
import { createHash } from 'crypto';

const CAP_SET=new Set(EFFECT_CAPABILITIES);
const sha256=(v)=>createHash('sha256').update(String(v)).digest('hex');

function freezeDeep(value){
  if(!value||typeof value!=='object'||Object.isFrozen(value))return value;
  for(const v of Object.values(value))freezeDeep(v);
  return Object.freeze(value);
}

export function validateCapabilityList(capabilities=[]){
  if(!Array.isArray(capabilities))throw new Error('capabilities must be an array');
  const out=[...new Set(capabilities.map(String))];
  for(const cap of out)if(!CAP_SET.has(cap))throw new Error(`unregistered base capability: ${cap}`);
  return out.sort();
}

export function normalizeToolSpec(raw={}){
  const tool_id=String(raw.tool_id||'').trim();
  const version=String(raw.version||'').trim();
  if(!tool_id||!version)throw new Error('ToolSpec requires tool_id and version');
  const capabilities=validateCapabilityList(raw.capabilities||[]);
  const spec={
    tool_id,version,
    provider:String(raw.provider||'').trim(),
    adapter_identity:String(raw.adapter_identity||'').trim(),
    lifecycle:String(raw.lifecycle||'ACTIVE').toUpperCase(),
    capabilities,
    resource_types:Array.isArray(raw.resource_types)?raw.resource_types.map(String):[],
    hidden_effects:Array.isArray(raw.hidden_effects)?raw.hidden_effects.map(String):[],
    consequential_parameters:Array.isArray(raw.consequential_parameters)?raw.consequential_parameters.map(String).sort():[],
    sandbox_profile:raw.sandbox_profile||null,
    egress_profile:raw.egress_profile||null,
    credential_profile:raw.credential_profile||null,
    idempotency:raw.idempotency||{mode:'NONE'},
    reconciliation:raw.reconciliation||{supported:false},
    read_qualification:raw.read_qualification||null,
    schema:raw.schema||{},
  };
  if(!['APPROVED','ACTIVE','WITHDRAWN','QUARANTINED'].includes(spec.lifecycle))throw new Error('invalid ToolSpec lifecycle');
  const spec_digest=sha256(stableJson(spec));
  return freezeDeep({...spec,spec_digest});
}

export function normalizeCapabilitySpec(raw={}){
  const capability_id=String(raw.capability_id||'').trim();
  const version=String(raw.version||'').trim();
  if(!capability_id||!version)throw new Error('CapabilitySpec requires capability_id and version');
  const spec={
    capability_id,version,
    semantic_action:String(raw.semantic_action||capability_id),
    base_capabilities:validateCapabilityList(raw.base_capabilities||[]),
    resource_types:Array.isArray(raw.resource_types)?raw.resource_types.map(String):[],
    constraints:raw.constraints||{},
  };
  return freezeDeep({...spec,spec_digest:sha256(stableJson(spec))});
}

export function createTrustedRegistry({toolSpecs=[],capabilitySpecs=[]}={}){
  const tools=new Map();
  const capabilities=new Map();
  for(const raw of toolSpecs){
    const spec=normalizeToolSpec(raw);const key=`${spec.tool_id}@${spec.version}`;
    if(tools.has(key))throw new Error(`duplicate ToolSpec ${key}`);tools.set(key,spec);
  }
  for(const raw of capabilitySpecs){
    const spec=normalizeCapabilitySpec(raw);const key=`${spec.capability_id}@${spec.version}`;
    if(capabilities.has(key))throw new Error(`duplicate CapabilitySpec ${key}`);capabilities.set(key,spec);
  }
  return Object.freeze({
    getTool(tool_id,version){return tools.get(`${tool_id}@${version}`)||null},
    getCapability(capability_id,version){return capabilities.get(`${capability_id}@${version}`)||null},
    snapshot(){return Object.freeze({tools:[...tools.values()],capabilities:[...capabilities.values()]})},
  });
}

export function readQualification(spec){
  if(!spec?.capabilities?.includes('READ'))return {qualified:false,reason:'READ capability is not declared'};
  const consequential=spec.hidden_effects?.filter(e=>['WRITE','DELETE','DEPLOY','SEND_EXTERNAL','PERMISSION_CHANGE','PRODUCTION_MUTATION'].includes(e))||[];
  if(consequential.length)return {qualified:false,reason:`consequential hidden effects declared: ${consequential.join(', ')}`};
  if(!spec.read_qualification?.evidence_ref)return {qualified:false,reason:'no version-bound READ qualification evidence'};
  return {qualified:true,reason:'registered READ path has version-bound qualification evidence'};
}
