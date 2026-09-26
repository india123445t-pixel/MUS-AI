const ARABIC_NUMBER_WORDS=Object.freeze({
  'واحدة':1,'واحد':1,'جملة':1,'سطر':1,
  'جملتين':2,'جملتان':2,'سطرين':2,'سطران':2,'اثنتين':2,'اثنان':2,'اثنين':2,'ثنتين':2,'ثنتان':2,
  'ثلاث':3,'ثلاثة':3,'ثلاثةً':3,'ثلاث جمل':3,'ثلاث أسطر':3,
  'أربع':4,'اربعة':4,'أربعة':4,'أربع جمل':4,'أربع أسطر':4,
  'خمس':5,'خمسة':5,'ست':6,'ستة':6,'سبع':7,'سبعة':7,'ثمان':8,'ثمانية':8,'تسع':9,'تسعة':9,'عشر':10,'عشرة':10,
});
const ENGLISH_NUMBER_WORDS=Object.freeze({one:1,two:2,three:3,four:4,five:5,six:6,seven:7,eight:8,nine:9,ten:10});
const GOVERNOR_PREFIXES=Object.freeze([
  Object.freeze({kind:'freshness',labels:Object.freeze(['تنبيه الدليل:','Evidence note:'])}),
  Object.freeze({kind:'execution',labels:Object.freeze(['حالة التنفيذ الموثقة:','Verified execution status:'])}),
  Object.freeze({kind:'action',labels:Object.freeze(['حالة الإجراء الخارجي:','External action status:'])}),
  Object.freeze({kind:'general',labels:Object.freeze(['حالة التحقق:','Verification status:'])}),
]);
const MIXED_DICTIONARY=Object.freeze({'تيمphu':'تيمفو','Thimphu':'تيمفو'});

function freeze(value){
  if(value&&typeof value==='object'&&!Object.isFrozen(value)){
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}

function normalizeDigits(value=''){
  const ar='٠١٢٣٤٥٦٧٨٩';
  return String(value).replace(/[٠-٩]/g,ch=>String(ar.indexOf(ch)));
}

function detectCount(text=''){
  const normalized=normalizeDigits(text);
  const numeric=normalized.match(/(?:^|\s)(\d{1,2})\s*(?:جمل(?:ة|تين|تان)?|أسطر|اسطر|سطر(?:ين|ان)?|sentences?|lines?)(?:\s|$|[،,.!?؟])/i)
    ||normalized.match(/(?:جمل(?:ة|تين|تان)?|أسطر|اسطر|سطر(?:ين|ان)?|sentences?|lines?)\s*(?::|=)?\s*(\d{1,2})/i);
  if(numeric){
    const n=Math.max(1,Math.min(20,Number(numeric[1])||0));
    if(n)return n;
  }
  const lower=normalized.toLowerCase();
  for(const [word,n] of Object.entries(ENGLISH_NUMBER_WORDS)){
    if(new RegExp(`\\b${word}\\s+(?:sentences?|lines?)\\b`,'i').test(lower))return n;
  }
  const compact=normalized.replace(/[\u064B-\u065F\u0670]/g,'');
  const arabicPatterns=[
    ['جملتين',2],['جملتان',2],['سطرين',2],['سطران',2],
    ['ثلاث جمل',3],['ثلاثة جمل',3],['ثلاث أسطر',3],['ثلاثة أسطر',3],
    ['أربع جمل',4],['اربعة جمل',4],['أربعة جمل',4],['أربع أسطر',4],['اربعة أسطر',4],['أربعة أسطر',4],
  ];
  for(const [pattern,n] of arabicPatterns)if(compact.includes(pattern))return n;
  for(const [word,n] of Object.entries(ARABIC_NUMBER_WORDS)){
    if(compact.includes(`${word} جملة`)||compact.includes(`${word} جمل`)||compact.includes(`${word} سطر`)||compact.includes(`${word} أسطر`))return n;
  }
  if(/\b(?:one|single)\s+(?:sentence|line)\b/i.test(lower)||/(?:جملة|سطر)\s+واحد(?:ة)?/.test(compact))return 1;
  return null;
}

export function extractFormatConstraints(rawInput=''){
  const text=String(rawInput||'');
  const lower=text.toLowerCase();
  const max_sentences=detectCount(text);
  const arNo=/(?:بدون|دون|لا\s+تضف|لا\s+تكتب|ممنوع|منع)\s*(?:أي\s*)?(?:مقدمة|تمهيد|تهنئة|خاتمة)/i.test(text);
  const enNo=/(?:without|no|do\s+not\s+(?:add|write|include))\s+(?:a\s+|any\s+)?(?:preamble|introduction|greeting|conclusion)/i.test(lower);
  const numbered_only=/(?:مرقم(?:ة)?\s+فقط|نقاط\s+مرقمة\s+فقط|قائمة\s+مرقمة\s+فقط|فقط\s+بترقيم|numbered\s+(?:list\s+)?only|only\s+(?:a\s+)?numbered\s+list)/i.test(text);
  return freeze({max_sentences,no_preamble:arNo||enNo,numbered_only,source:'user_text'});
}

function prefixKind(line=''){
  const t=String(line||'').trim();
  for(const item of GOVERNOR_PREFIXES){
    if(item.labels.some(label=>t.startsWith(label)))return item.kind;
  }
  return null;
}

export function collapseDuplicatePrefixes(text=''){
  const lines=String(text||'').replace(/\r\n?/g,'\n').split('\n');
  const out=[];
  let collapsed_count=0;
  let previousKind=null;
  for(const line of lines){
    const kind=prefixKind(line);
    if(kind&&kind===previousKind){collapsed_count++;continue;}
    out.push(line);
    previousKind=kind;
    if(!kind&&line.trim())previousKind=null;
  }
  return freeze({text:out.join('\n'),collapsed_count});
}

function splitGovernorHead(text=''){
  const lines=String(text||'').replace(/\r\n?/g,'\n').split('\n');
  const head=[];
  let index=0;
  while(index<lines.length){
    if(prefixKind(lines[index])){head.push(lines[index]);index++;continue;}
    if(!lines[index].trim()&&head.length){head.push(lines[index]);index++;continue;}
    break;
  }
  return {head,body:lines.slice(index)};
}

function looksLikePreamble(line=''){
  const t=String(line||'').trim();
  if(!t)return true;
  return /^(?:(?:بالطبع|بالتأكيد|أكيد|حسنًا|حسناً|إليك|تفضل|تمام|يسعدني|سأجيب|سأوضح|فيما يلي|طبعًا|طبعا)[\s,:،-]*|(?:sure|certainly|of course|here(?:'s| is| are)|absolutely|okay|ok|i(?:'ll| will)\s+(?:answer|explain)|the answer is)\b[\s,:-]*)/i.test(t);
}

function trimPreamble(body=[]){
  const firstNumbered=body.findIndex(line=>/^\s*(?:[0-9٠-٩]+[.)\-:]|[-*]\s*[0-9٠-٩]+[.)\-:]?)\s+/.test(line));
  if(firstNumbered>0)return {lines:body.slice(firstNumbered),removed:firstNumbered};
  let idx=0;
  while(idx<body.length&&looksLikePreamble(body[idx]))idx++;
  return {lines:body.slice(idx),removed:idx};
}

function limitSentences(text='',max=0){
  const source=String(text||'').trim();
  if(!max||!source)return {text:source,trimmed:false};
  const matches=[...source.matchAll(/[^.!?؟\n]+(?:[.!?؟]+|(?=\n|$))/g)].map(m=>m[0].trim()).filter(Boolean);
  if(matches.length<=max)return {text:source,trimmed:false};
  return {text:matches.slice(0,max).join(' ').trim(),trimmed:true};
}

export function enforceFormatConstraints({text='',constraints={}}={}){
  const c=constraints&&typeof constraints==='object'?constraints:{};
  const applied=[];
  let violations_fixed=0;
  const parts=splitGovernorHead(text);
  let body=parts.body;
  if(c.no_preamble===true){
    const trimmed=trimPreamble(body);
    body=trimmed.lines;
    applied.push('no_preamble');
    if(trimmed.removed>0)violations_fixed++;
  }
  let bodyText=body.join('\n').trim();
  if(Number(c.max_sentences)>0){
    const limited=limitSentences(bodyText,Math.max(1,Math.min(20,Number(c.max_sentences))));
    bodyText=limited.text;
    applied.push('max_sentences');
    if(limited.trimmed)violations_fixed++;
  }
  const head=parts.head.join('\n').trimEnd();
  const joined=[head,bodyText].filter(Boolean).join(head&&bodyText?'\n\n':'');
  return freeze({text:joined,applied,violations_fixed});
}

export function fixMixedScriptWords(text=''){
  let output=String(text||'');
  for(const [from,to] of Object.entries(MIXED_DICTIONARY))output=output.replace(new RegExp(from.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'),to);
  const notes=[];
  const seen=new Set();
  const tokens=output.match(/[\u0600-\u06ffA-Za-z][\u0600-\u06ffA-Za-z_-]*/g)||[];
  for(const token of tokens){
    if(/[\u0600-\u06ff]/.test(token)&&/[A-Za-z]/.test(token)&&!seen.has(token)){
      seen.add(token);
      notes.push(`unknown_mixed_script:${token}`);
    }
  }
  return freeze({text:output,notes});
}
