import { redactSecrets } from './security.js';
import { VERIFICATION_RESULTS } from './constants.js';

function prefix(language,kind){
  const ar=language==='ar';
  if(kind==='freshness')return ar?'تنبيه الدليل: لا أستطيع تأكيد أن المعلومات الآتية حديثة/حالية من مصدر خارجي موثوق في هذه الجولة.':'Evidence note: I cannot confirm that the following information is current from authoritative external evidence in this run.';
  if(kind==='execution')return ar?'حالة التنفيذ الموثقة: لم يُسجَّل تنفيذ خارجي أو اختبار فعلي يمكنني إثباته في هذه الجولة.':'Verified execution status: no external execution or real test run is recorded as proven in this run.';
  if(kind==='action')return ar?'حالة الإجراء الخارجي: هذه المحادثة لم تنفّذ الإجراء المطلوب؛ النص أدناه اقتراح/خطة فقط ما لم يوجد إيصال وتنفيذ موثّق.':'External action status: this chat did not execute the requested side effect; the text below is a proposal/plan unless an actual bound receipt and verification exist.';
  return ar?'حالة التحقق: النتيجة غير محسومة رسميًا؛ سأفصل بين ما أعرفه وما لم أتحقق منه.':'Verification status: the result is not formally resolved; I will separate supported content from unverified content.';
}

export function governResponse({text,contract,verification,deterministic={}}){
  let body=redactSecrets(String(text||'').trim());
  const notes=[];
  const unresolved=verification?.required&&verification?.result!==VERIFICATION_RESULTS.VERIFIED;

  if(contract?.external_evidence_required&&verification?.result!==VERIFICATION_RESULTS.VERIFIED){
    notes.push(prefix(contract.language,'freshness'));
  }
  if(contract?.domains?.includes('software')&&!deterministic.executionEvidence){
    notes.push(prefix(contract.language,'execution'));
  }
  if(contract?.externally_actionable&&!deterministic.postconditionEvidence){
    notes.push(prefix(contract.language,'action'));
  }
  if(unresolved&&!notes.length&&contract?.high_consequence){
    notes.push(prefix(contract.language,'general'));
  }

  const unique=[...new Set(notes)];
  if(unique.length)body=`${unique.join('\n')}\n\n${body}`;
  return Object.freeze({text:body,notes:unique,formal_result:verification?.result||null});
}
