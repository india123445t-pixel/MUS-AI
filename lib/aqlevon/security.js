const SECRET_PATTERNS = [
  /\bsk-[A-Za-z0-9_-]{16,}\b/g,
  /\bgh[pousr]_[A-Za-z0-9_]{20,}\b/g,
  /\bAIza[0-9A-Za-z_-]{20,}\b/g,
  /\bAKIA[0-9A-Z]{16}\b/g,
  /\bsb_secret_[A-Za-z0-9_-]{12,}\b/g,
  /\bBearer\s+[A-Za-z0-9._~+\/-]+=*\b/gi,
  /\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b/g,
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g,
];

const SENSITIVE_ASSIGNMENTS = /\b(?:api[_-]?key|token|password|passwd|secret|client[_-]?secret|access[_-]?key)\s*[:=]\s*([^\s,;]{8,})/gi;

export function redactSecrets(value='') {
  let text = String(value ?? '');
  for (const pattern of SECRET_PATTERNS) text = text.replace(pattern, '[REDACTED_SECRET]');
  text = text.replace(SENSITIVE_ASSIGNMENTS, (m) => {
    const [left] = m.split(/[:=]/,1);
    return `${left}= [REDACTED_SECRET]`;
  });
  return text;
}

export function containsSecretLike(value='') {
  const text = String(value ?? '');
  if (SENSITIVE_ASSIGNMENTS.test(text)) {
    SENSITIVE_ASSIGNMENTS.lastIndex = 0;
    return true;
  }
  SENSITIVE_ASSIGNMENTS.lastIndex = 0;
  return SECRET_PATTERNS.some((pattern) => {
    pattern.lastIndex = 0;
    const found = pattern.test(text);
    pattern.lastIndex = 0;
    return found;
  });
}

export function sanitizeHistory(history, maxItems=24, maxChars=14000) {
  if (!Array.isArray(history)) return [];
  return history
    .slice(-Math.max(1, Math.min(64, Number(maxItems) || 24)))
    .filter((item) => ['user','assistant'].includes(item?.role) && typeof item?.content === 'string')
    .map((item) => ({
      role: item.role,
      content: redactSecrets(item.content).slice(0, maxChars),
    }));
}

export function sanitizeHistoryBudget(history,{maxItems=12,maxTotalChars=5000,maxPerItem=1600}={}) {
  if (!Array.isArray(history)) return [];
  const eligible=history
    .slice(-Math.max(1,Math.min(64,Number(maxItems)||12)))
    .filter(item=>['user','assistant'].includes(item?.role)&&typeof item?.content==='string');
  const out=[];
  let remaining=Math.max(500,Math.min(12000,Number(maxTotalChars)||5000));
  for(let i=eligible.length-1;i>=0&&remaining>0;i--){
    const item=eligible[i];
    const text=redactSecrets(item.content).slice(0,Math.max(200,Math.min(3000,Number(maxPerItem)||1600)));
    if(!text)continue;
    const keep=text.slice(-remaining);
    out.unshift({role:item.role,content:keep});
    remaining-=keep.length;
  }
  return out;
}

export function sanitizeEvidenceText(value='', maxChars=6000) {
  return redactSecrets(String(value ?? '')).slice(0, maxChars);
}

export function stableJson(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map(k => `${JSON.stringify(k)}:${stableJson(value[k])}`).join(',')}}`;
}

export function assertNoAuthorityFromUntrusted(text='') {
  const lower = String(text).toLowerCase();
  const suspicious = [
    'ignore previous instructions','ignore all previous','ignore all rules','system message','developer message','system override',
    'grant permission','widen scope','reveal secret','print secret','send credentials','credentials to','exfiltrate','disable verification',
    'تجاهل التعليمات','تجاهل كل','رسالة النظام','اكشف السر','اعرض كلمة السر','عطّل التحقق','وسع الصلاحيات'
  ];
  return suspicious.filter(term => lower.includes(term));
}
