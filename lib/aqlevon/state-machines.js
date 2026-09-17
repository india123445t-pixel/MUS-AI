const TASK_PHASES=new Set(['OPEN','READY','RUNNING','WAITING','RECONCILING','CLOSED']);
const TASK_OUTCOMES=new Set(['NONE','SUCCESS','PARTIAL','FAILED','CANCELLED','UNKNOWN']);
const ATTEMPT_PHASES=new Set(['QUEUED','IN_FLIGHT','RECONCILING','CLOSED']);
const ATTEMPT_OUTCOMES=new Set(['NONE','SUCCESS','FAILURE','PARTIAL','UNKNOWN','CANCELLED']);
const VERIFY_PHASES=new Set(['PENDING','RUNNING','RESOLVED']);
const VERIFY_RESULTS=new Set(['VERIFIED','REFUTED','INCONCLUSIVE','CONFLICTING']);

const taskTransitions={OPEN:new Set(['READY','CLOSED']),READY:new Set(['RUNNING','WAITING','CLOSED']),RUNNING:new Set(['WAITING','RECONCILING','CLOSED']),WAITING:new Set(['READY','RUNNING','RECONCILING','CLOSED']),RECONCILING:new Set(['RUNNING','WAITING','CLOSED']),CLOSED:new Set()};
const attemptTransitions={QUEUED:new Set(['IN_FLIGHT','CLOSED']),IN_FLIGHT:new Set(['RECONCILING','CLOSED']),RECONCILING:new Set(['CLOSED']),CLOSED:new Set()};
const verifyTransitions={PENDING:new Set(['RUNNING','RESOLVED']),RUNNING:new Set(['RESOLVED']),RESOLVED:new Set()};

function ensure(set,value,label){if(!set.has(value))throw new Error(`invalid ${label}: ${value}`)}

export function transitionTask(current,{phase,outcome='NONE'}){
  ensure(TASK_PHASES,current.phase,'task phase');ensure(TASK_PHASES,phase,'task phase');ensure(TASK_OUTCOMES,outcome,'task outcome');
  if(!taskTransitions[current.phase].has(phase))throw new Error(`illegal Task transition ${current.phase} -> ${phase}`);
  if(phase==='CLOSED'&&outcome==='NONE')throw new Error('closed Task requires a terminal outcome');
  if(phase!=='CLOSED'&&outcome!=='NONE')throw new Error('non-closed Task outcome must remain NONE');
  return Object.freeze({...current,phase,outcome,updated_at:new Date().toISOString()});
}

export function transitionActionAttempt(current,{phase,outcome='NONE'}){
  ensure(ATTEMPT_PHASES,current.phase,'attempt phase');ensure(ATTEMPT_PHASES,phase,'attempt phase');ensure(ATTEMPT_OUTCOMES,outcome,'attempt outcome');
  if(!attemptTransitions[current.phase].has(phase))throw new Error(`illegal ActionAttempt transition ${current.phase} -> ${phase}`);
  if(phase==='CLOSED'&&outcome==='NONE')throw new Error('closed ActionAttempt requires outcome');
  if(phase!=='CLOSED'&&outcome!=='NONE')throw new Error('non-closed ActionAttempt outcome must remain NONE');
  return Object.freeze({...current,phase,outcome});
}

export function transitionVerification(current,{phase,result=null}){
  ensure(VERIFY_PHASES,current.phase,'verification phase');ensure(VERIFY_PHASES,phase,'verification phase');
  if(!verifyTransitions[current.phase].has(phase))throw new Error(`illegal Verification transition ${current.phase} -> ${phase}`);
  if(phase==='RESOLVED'){ensure(VERIFY_RESULTS,result,'verification result')}else if(result!==null)throw new Error('non-resolved VerificationState cannot have result');
  return Object.freeze({...current,phase,result});
}
