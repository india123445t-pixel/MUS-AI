export const CHILD_EVAL_SCHEMA='AQLEVON_CHILD_CANDIDATE_EVAL_V1';

function norm(s){return String(s||'').trim().toLowerCase().replace(/\s+/g,' ')}

export function evaluateChildTeachingCandidate(candidate){
  const issues=[];
  const warnings=[];
  const examples=Array.isArray(candidate?.examples)?candidate.examples:[];
  const lessons=Array.isArray(candidate?.lessons)?candidate.lessons:[];
  const trials=candidate?.trial_summary||{total:0,pass:0,fail:0};

  if(candidate?.schema!=='AQLEVON_CHILD_TEACHING_CANDIDATE_V1')issues.push('SCHEMA_INVALID');
  if(candidate?.scope!=='child-lab-only')issues.push('SCOPE_INVALID');
  if(candidate?.isolation?.production_weight_write!==false)issues.push('PRODUCTION_WRITE_FORBIDDEN');
  if(candidate?.isolation?.training_lane_write!==false)issues.push('TRAINING_LANE_WRITE_FORBIDDEN');
  if(candidate?.isolation?.worker03_access!==false)issues.push('WORKER03_ACCESS_FORBIDDEN');
  if(candidate?.isolation?.automatic_promotion!==false)issues.push('AUTO_PROMOTION_FORBIDDEN');
  if(!candidate?.candidate_sha256||!/^[a-f0-9]{64}$/.test(candidate.candidate_sha256))issues.push('CANDIDATE_HASH_INVALID');
  if(examples.length<1)issues.push('NO_EXAMPLES');
  if(examples.length<3)warnings.push('LOW_EXAMPLE_COUNT');
  if(lessons.length<1)warnings.push('NO_EXPLICIT_LESSONS');

  const seen=new Set();
  let duplicates=0,preferredSame=0;
  for(const row of examples){
    const key=norm(row?.input);
    if(!key)issues.push('EMPTY_INPUT');
    else if(seen.has(key))duplicates++;
    else seen.add(key);
    if(norm(row?.child_answer)&&norm(row?.child_answer)===norm(row?.preferred_answer))preferredSame++;
    if(!norm(row?.preferred_answer))issues.push('EMPTY_PREFERRED_ANSWER');
    if(row?.source!=='child-lab-only')issues.push('EXAMPLE_SCOPE_INVALID');
  }
  if(duplicates>0)warnings.push('DUPLICATE_INPUTS');
  if(preferredSame>0)warnings.push('UNCHANGED_CORRECTIONS');

  const passRate=trials.total>0?trials.pass/trials.total:null;
  if(trials.total===0)warnings.push('NO_TRIAL_EVIDENCE');
  if(passRate!==null&&passRate<0.5)warnings.push('LOW_TRIAL_PASS_RATE');

  const qualityScore=Math.max(0,100
    - issues.length*30
    - (examples.length<3?15:0)
    - Math.min(20,duplicates*5)
    - Math.min(20,preferredSame*5)
    - (trials.total===0?10:0)
    - (passRate!==null&&passRate<0.5?15:0)
  );

  const verdict=issues.length?'REJECT':qualityScore>=80?'READY_FOR_CHILD_EVAL':qualityScore>=60?'NEEDS_MORE_TEACHING':'REJECT';
  return Object.freeze({
    schema:CHILD_EVAL_SCHEMA,
    candidate_sha256:candidate?.candidate_sha256||null,
    valid:issues.length===0,
    issues:Object.freeze([...new Set(issues)]),
    warnings:Object.freeze([...new Set(warnings)]),
    metrics:Object.freeze({
      example_count:examples.length,
      lesson_count:lessons.length,
      trial_total:Number(trials.total||0),
      trial_pass:Number(trials.pass||0),
      trial_fail:Number(trials.fail||0),
      trial_pass_rate:passRate,
      duplicate_inputs:duplicates,
      unchanged_corrections:preferredSame,
      quality_score:qualityScore,
    }),
    verdict,
    training_allowed:false,
    gpu_allowed:false,
    production_weight_write:false,
    training_lane_write:false,
    worker03_access:false,
  });
}
