import crypto from 'node:crypto';

export const CHILD_CANDIDATE_SCHEMA='AQLEVON_CHILD_TEACHING_CANDIDATE_V1';

function stable(value){
  if(Array.isArray(value))return value.map(stable);
  if(value&&typeof value==='object'){
    const out={};for(const k of Object.keys(value).sort())out[k]=stable(value[k]);return out;
  }
  return value;
}

function sha256(value){
  return crypto.createHash('sha256').update(typeof value==='string'?value:JSON.stringify(stable(value))).digest('hex');
}

export function childCandidateHashPayload(candidate={}){
  return {
    schema:candidate.schema,
    scope:candidate.scope,
    persona:candidate.persona,
    lessons:candidate.lessons,
    examples:candidate.examples,
    trial_summary:candidate.trial_summary,
    isolation:candidate.isolation,
  };
}

export function computeChildCandidateSha256(candidate={}){
  return sha256(childCandidateHashPayload(candidate));
}

export function normalizeChildExample(row){
  if(!row||typeof row!=='object')throw new Error('EXAMPLE_INVALID');
  const input=String(row.input||'').trim();
  const preferred=String(row.preferred_answer||'').trim();
  if(!input||!preferred)throw new Error('EXAMPLE_REQUIRED_FIELDS');
  if(input.length>12000||preferred.length>12000)throw new Error('EXAMPLE_TOO_LARGE');
  return Object.freeze({
    schema:'AQLEVON_CHILD_TEACHING_EXAMPLE_V1',
    input,
    child_answer:String(row.child_answer||'').slice(0,12000),
    preferred_answer:preferred,
    persona_snapshot:String(row.persona_snapshot||'').slice(0,12000),
    source:'child-lab-only',
    production_weight_write:false,
    training_lane_write:false,
  });
}

export function buildChildTeachingCandidate({persona='',lessons=[],examples=[],trials=[]}={}){
  const normalizedExamples=examples.map(normalizeChildExample);
  if(normalizedExamples.length<1)throw new Error('NO_TEACHING_EXAMPLES');
  const body={
    schema:CHILD_CANDIDATE_SCHEMA,
    created_at:new Date().toISOString(),
    scope:'child-lab-only',
    persona:String(persona||'').slice(0,12000),
    lessons:(lessons||[]).slice(0,200).map(x=>String(x?.text??x??'').slice(0,2000)).filter(Boolean),
    examples:normalizedExamples,
    trial_summary:{
      total:(trials||[]).length,
      pass:(trials||[]).filter(x=>x?.result==='PASS').length,
      fail:(trials||[]).filter(x=>x?.result==='FAIL').length,
    },
    isolation:{
      public_model_access:false,
      production_weight_write:false,
      training_lane_write:false,
      worker03_access:false,
      automatic_promotion:false,
    },
  };
  return Object.freeze({...body,candidate_sha256:computeChildCandidateSha256(body)});
}

export function evaluateChildCandidate(candidate){
  const issues=[];
  if(candidate?.schema!==CHILD_CANDIDATE_SCHEMA)issues.push('SCHEMA_INVALID');
  if(candidate?.scope!=='child-lab-only')issues.push('SCOPE_INVALID');
  if(candidate?.isolation?.production_weight_write!==false)issues.push('PRODUCTION_WRITE_FORBIDDEN');
  if(candidate?.isolation?.training_lane_write!==false)issues.push('TRAINING_LANE_WRITE_FORBIDDEN');
  if(candidate?.isolation?.worker03_access!==false)issues.push('WORKER03_ACCESS_FORBIDDEN');
  if(candidate?.isolation?.automatic_promotion!==false)issues.push('AUTOMATIC_PROMOTION_FORBIDDEN');
  if(!candidate?.candidate_sha256||!/^[a-f0-9]{64}$/.test(candidate.candidate_sha256))issues.push('CANDIDATE_HASH_INVALID');
  else if(candidate.candidate_sha256!==computeChildCandidateSha256(candidate))issues.push('CANDIDATE_HASH_MISMATCH');
  if(!Array.isArray(candidate?.examples)||candidate.examples.length<1)issues.push('NO_EXAMPLES');
  const passRate=candidate?.trial_summary?.total>0?candidate.trial_summary.pass/candidate.trial_summary.total:null;
  return Object.freeze({
    valid:issues.length===0,
    issues:Object.freeze(issues),
    example_count:candidate?.examples?.length||0,
    pass_rate:passRate,
    recommendation:issues.length?'REJECT':'EVAL_REQUIRED',
  });
}
