export const CURRENT_VERIFICATION_RESULTS = Object.freeze(['VERIFIED','REFUTED','INCONCLUSIVE','CONFLICTING']);

export function verificationResult(verification={}){
  const result=String(verification?.result||'').toUpperCase();
  return CURRENT_VERIFICATION_RESULTS.includes(result)?result:null;
}

export function isVerifiedTrace(log={}){
  return verificationResult(log.verification)==='VERIFIED';
}

export function isUnresolvedTrace(log={}){
  return ['INCONCLUSIVE','CONFLICTING'].includes(verificationResult(log.verification));
}

export function isDeepRoute(log={}){
  return log?.route_decision?.reasoning==='deep';
}

export function traceDomain(log={}){
  const contract=log?.task_contract||{};
  return contract.primary_domain||(Array.isArray(contract.domains)?contract.domains[0]:null)||'general';
}

export function verificationLabel(verification={}){
  const current=verificationResult(verification);
  if(current)return current;
  const legacy=String(verification?.verdict||'').trim();
  return legacy?`LEGACY_${legacy.toUpperCase()}`:'—';
}

export function advisoryConfidence(verification={}){
  const n=verification?.advisory?.confidence;
  return Number.isFinite(Number(n))?Number(n):null;
}

export function formalLearningEligible(log={}){
  return isVerifiedTrace(log)&&log.learning_eligible===true;
}
