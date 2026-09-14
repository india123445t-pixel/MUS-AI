import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createHash, randomUUID } from 'crypto';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function client(){if(!SUPABASE_URL||!SUPABASE_KEY)throw new Error('Supabase environment is not configured.');return createClient(SUPABASE_URL,SUPABASE_KEY,{auth:{persistSession:false}})}
function isUuid(v=''){return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(v))}
function normalizeEndpoint(raw){if(!raw)return null;const url=raw.replace(/\/$/,'');if(url.endsWith('/chat/completions'))return url;if(url.endsWith('/v1'))return `${url}/chat/completions`;return url}
function clamp(n,min,max){return Math.max(min,Math.min(max,Number(n)||0))}
function includesAny(text,terms){return terms.some(t=>text.includes(t))}
function safeJson(text){try{return JSON.parse(String(text||'').replace(/^```json\s*/i,'').replace(/```\s*$/,'').trim())}catch{}try{const s=String(text||'');const a=s.indexOf('{'),b=s.lastIndexOf('}');if(a>=0&&b>a)return JSON.parse(s.slice(a,b+1))}catch{}return null}
function extractCitations(message){return (message?.annotations||[]).filter(a=>a?.type==='url_citation'&&a?.url_citation?.url).slice(0,8).map(a=>({url:String(a.url_citation.url),title:String(a.url_citation.title||''),content:String(a.url_citation.content||'').slice(0,1800)}))}

async function loadRuntime(sb){
  const [cfg,lessons]=await Promise.all([sb.rpc('get_mus_runtime_config'),sb.rpc('get_mus_runtime_lessons',{p_limit:18})]);
  return {settings:cfg.data||{},lessons:lessons.data||[]};
}

function buildTaskContract(input){
  const l=input.toLowerCase();
  const lines=(input.match(/\n/g)||[]).length;
  const coding=includesAny(l,['javascript','typescript','python','react','next.js','sql',' api ','function','github','repository','debug','bug',' code ','برمج','كود','دالة','خوارزم','برنامج','يطبع','for each','foreach','async','await','left join']);
  const math=includesAny(l,['math','equation','proof','probability','algebra','geometry','modulo','mod ','رياضيات','معادلة','احسب','حساب','برهان','احتمال','نسبة مئوية','باقي قسمة','قسمة','قوى','الأس','أس ']);
  const science=includesAny(l,['physics','chemistry','biology','gravity','acceleration','temperature','energy','mass','vacuum','orbit','فيزياء','كيمياء','أحياء','جاذبية','تسارع','درجة الحرارة','الحرارة','طاقة','كتلة','فراغ','مدار','رواد الفضاء']);
  const language=includesAny(l,['grammar','rewrite','pronoun','ambiguity','translation','الجملة','أعد صياغة','صياغة','ضمير','غموض','المعنى','لغة','نحو','ترجمة']);
  const planning=includesAny(l,['architecture','roadmap','strategy','planning','schedule','dependency','dependencies','project plan','معمارية','خطة','استراتيجية','خارطة طريق','الجدولة','المهام','يعتمد على','تعتمد على','أقل زمن','عاملان','مهمة ','مشروع فيه المهام']);
  const reasoning=includesAny(l,['logic','deduce','necessarily','puzzle','reasoning','منطق','نستنتج','حتمًا','لغز','استدلال','كل a','لا شيء من']);
  const research=includesAny(l,['research','sources','source','citation','documentation','benchmark','study','evidence','ابحث','بحث','مصادر','مصدر','وثائق','دراسة','دليل']);
  const freshness=includesAny(l,['latest','current','today','now','recent','price','weather','news','2026','اليوم','الآن','حالي','أحدث','آخر إصدار','سعر','طقس','أخبار']);
  const highRisk=includesAny(l,['diagnosis','dose','prescription','lawsuit','legal advice','investment advice','medical','تشخيص','جرعة','دواء','استشارة قانونية','قانوني','استثمار','طبي']);

  let domain='general';
  if(coding)domain='coding';else if(math)domain='math';else if(science)domain='science';else if(planning)domain='planning';else if(research)domain='research';else if(reasoning)domain='reasoning';else if(language)domain='language';

  const structured=lines>=4||includesAny(l,['يعتمد على','تعتمد على','depends on','constraint','constraints','قيود']);
  let score=0;
  if(input.length>900)score++;
  if(coding||math||science||planning||research||reasoning)score++;
  if(structured&&(coding||planning))score+=2;else if(structured)score++;
  if(includesAny(l,['step by step','deep','complex','hard','optimize','production','security','دقيق','بعمق','معقد','احترافي','أقوى','أمان','إنتاجي']))score++;
  if((input.match(/[?؟]/g)||[]).length>=3)score++;
  const difficulty=score>=3?'hard':score>=1?'normal':'easy';
  const requiresVerification=coding||math||science||planning||research||reasoning||highRisk;

  return {
    domain,difficulty,language:/[\u0600-\u06ff]/.test(input)?'ar':'other',
    requires_web:freshness||research,freshness_required:freshness,
    requires_verification:requiresVerification,high_risk:highRisk,
    structured_input:structured,
    success_criteria:[
      'Answer the user request directly',
      'Preserve named entities, task labels, quantities, dependencies, and constraints exactly',
      'Do not invent facts, sources, executions, or tool results',
      ...(freshness?['Current claims require current evidence or an explicit uncertainty statement']:[]),
      ...(coding?['Do not claim code execution unless real execution evidence exists']:[]),
      ...(math?['Recheck arithmetic and constraints before finalizing']:[]),
      ...(planning?['Normalize task names, durations, dependencies, resources, and objective before solving']:[])
    ]
  };
}

async function selfHosted(messages,settings,opts={}){
  if((opts.excludeProviders||[]).includes('mus-engine'))return null;
  const endpoint=normalizeEndpoint(process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL);if(!endpoint)return null;
  try{
    const key=process.env.MUS_MODEL_KEY||process.env.LOCAL_MODEL_KEY;
    const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json',...(key?{Authorization:`Bearer ${key}`}:{})},body:JSON.stringify({model:settings?.self_hosted_model||process.env.MUS_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'mus-ai',messages,temperature:Number(opts.temperature??settings?.temperature??0.6),stream:false}),signal:AbortSignal.timeout(65000)});
    if(!r.ok)return null;const d=await r.json();const message=d?.choices?.[0]?.message||null;const text=message?.content||d?.message?.content||d?.response||null;
    return text?{text,provider:'mus-engine',model:d?.model||settings?.self_hosted_model||'MUS AI',citations:[]}:null;
  }catch{return null}
}

async function openAICompatible({key,url,model,provider,messages,temperature=0.6,headers={},payloadExtra={}}){
  if(!key)return null;
  try{
    const r=await fetch(url,{method:'POST',headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json',...headers},body:JSON.stringify({model,messages,temperature,stream:false,...payloadExtra}),signal:AbortSignal.timeout(75000)});
    const d=await r.json().catch(()=>null);if(!r.ok||!d)return null;
    const message=d?.choices?.[0]?.message||{};const text=message?.content||null;
    return text?{text,provider,model:d?.model||model,citations:extractCitations(message)}:null;
  }catch{return null}
}

async function openRouter(messages,webSearch,settings,opts={}){
  const key=process.env.OPENROUTER_API_KEY;if(!key)return null;
  let model=settings?.openrouter_model||process.env.OPENROUTER_MODEL||'openrouter/free';
  if(!settings?.allow_paid_external&&!String(model).includes(':free')&&model!=='openrouter/free')model='openrouter/free';
  const payloadExtra={};
  if(webSearch&&settings?.allow_paid_external&&settings?.public_web_search_enabled)payloadExtra.plugins=[{id:'web',max_results:5}];
  return openAICompatible({key,url:'https://openrouter.ai/api/v1/chat/completions',model,provider:'openrouter',messages,temperature:Number(opts.temperature??settings?.temperature??0.6),headers:{'X-Title':'MUS AI'},payloadExtra});
}
async function groq(messages,settings,opts={}){return openAICompatible({key:process.env.GROQ_API_KEY,url:'https://api.groq.com/openai/v1/chat/completions',model:process.env.GROQ_MODEL||'openai/gpt-oss-120b',provider:'groq',messages,temperature:Number(opts.temperature??settings?.temperature??0.6),payloadExtra:{reasoning_effort:Number(opts.temperature??0.6)<=0.15?'low':'medium'}})}
async function mistral(messages,settings,opts={}){return openAICompatible({key:process.env.MISTRAL_API_KEY,url:'https://api.mistral.ai/v1/chat/completions',model:process.env.MISTRAL_MODEL||'mistral-small-latest',provider:'mistral',messages,temperature:Number(opts.temperature??settings?.temperature??0.6)})}
async function cerebras(messages,settings,opts={}){return openAICompatible({key:process.env.CEREBRAS_API_KEY,url:'https://api.cerebras.ai/v1/chat/completions',model:process.env.CEREBRAS_MODEL||'gpt-oss-120b',provider:'cerebras',messages,temperature:Number(opts.temperature??settings?.temperature??0.6),headers:{'X-Cerebras-Version-Patch':'2'}})}
async function huggingFace(messages,settings,opts={}){if(process.env.HF_FREE_FALLBACK_ENABLED!=='true')return null;return openAICompatible({key:process.env.HF_TOKEN,url:'https://router.huggingface.co/v1/chat/completions',model:process.env.HF_MODEL||'openai/gpt-oss-120b:cheapest',provider:'huggingface',messages,temperature:Number(opts.temperature??settings?.temperature??0.6)})}
async function gemini(messages,settings,opts={}){
  const key=process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY;if(!key)return null;
  try{
    const model=process.env.GEMINI_MODEL||'gemini-2.5-flash';
    const systemParts=messages.filter(m=>m.role==='system').map(m=>String(m.content||''));
    const contents=messages.filter(m=>m.role!=='system').map(m=>({role:m.role==='assistant'?'model':'user',parts:[{text:String(m.content||'')}]}));
    const body={contents,generationConfig:{temperature:Number(opts.temperature??settings?.temperature??0.6)},...(systemParts.length?{systemInstruction:{parts:[{text:systemParts.join('\n\n')}]} }:{})};
    const r=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':key},body:JSON.stringify(body),signal:AbortSignal.timeout(75000)});
    const d=await r.json().catch(()=>null);if(!r.ok||!d)return null;
    const parts=d?.candidates?.[0]?.content?.parts||[];const text=parts.map(p=>p?.text||'').join('').trim();
    return text?{text,provider:'gemini',model,citations:[]}:null;
  }catch{return null}
}

async function externalFreeFallback(messages,webSearch,settings,opts={}){
  const excluded=new Set(opts.excludeProviders||[]);
  const providers=[
    ['openrouter',()=>openRouter(messages,webSearch,settings,opts)],
    ['groq',()=>groq(messages,settings,opts)],
    ['gemini',()=>gemini(messages,settings,opts)],
    ['mistral',()=>mistral(messages,settings,opts)],
    ['cerebras',()=>cerebras(messages,settings,opts)],
    ['huggingface',()=>huggingFace(messages,settings,opts)]
  ];
  for(const [name,run] of providers){if(excluded.has(name))continue;try{const r=await run();if(r)return r}catch{}}
  return null;
}
async function generate(messages,webSearch,settings,opts={}){
  const mode=settings?.runtime_mode||'openrouter_primary';
  if(mode==='self_hosted_only')return selfHosted(messages,settings,opts);
  if(mode==='self_hosted_primary')return await selfHosted(messages,settings,opts)||await externalFreeFallback(messages,webSearch,settings,opts);
  return await externalFreeFallback(messages,webSearch,settings,opts)||await selfHosted(messages,settings,opts);
}

function normalizeVerification(raw){
  if(!raw||typeof raw!=='object')return {verdict:'unresolved',confidence:0,issues:['Verifier output was not parseable']};
  let verdict=String(raw.verdict||'unresolved').toLowerCase();if(!['pass','repair','uncertain','unresolved'].includes(verdict))verdict='unresolved';
  return {verdict,confidence:clamp(raw.confidence,0,1),issues:Array.isArray(raw.issues)?raw.issues.slice(0,6).map(String):[],corrected_answer:typeof raw.corrected_answer==='string'?raw.corrected_answer.trim():'',preferred:['A','B'].includes(raw.preferred)?raw.preferred:null};
}

async function verifyCandidate({input,contract,candidates,settings,webSearch}){
  if(contract.requires_web&&!webSearch)return {verdict:'uncertain',confidence:0.30,issues:['Current/source evidence is unavailable under the current zero-cost policy.'],independent:false};
  const excluded=[...new Set(candidates.map(c=>c.provider).filter(Boolean))];
  const verifierSystem=`You are an independent MUS AI verifier. Judge correctness and constraint satisfaction, not style. Preserve task labels and quantities exactly. Solve the problem independently when practical. Never claim code execution without execution evidence. Return STRICT JSON only: {"verdict":"pass|repair|uncertain","confidence":0.0,"issues":["short issue"],"preferred":"A|B|null","corrected_answer":"only if a concrete correction is necessary"}.`;
  const payload={task:input,task_contract:contract,candidates:candidates.map((c,i)=>({label:String.fromCharCode(65+i),answer:c.text,citations:c.citations||[]}))};
  const r=await generate([{role:'system',content:verifierSystem},{role:'user',content:JSON.stringify(payload)}],webSearch,settings,{temperature:0.1,excludeProviders:excluded});
  if(!r)return {verdict:'unresolved',confidence:0,issues:['No independent verifier available'],independent:false};
  const v=normalizeVerification(safeJson(r.text));
  return {...v,verifier_provider:r.provider,verifier_model:r.model,independent:!excluded.includes(r.provider)};
}

async function adjudicateRepair({input,contract,original,corrected,settings,webSearch,excludeProviders=[]}){
  const system='You are a final independent adjudicator. Compare ORIGINAL and CORRECTED against the task. Return STRICT JSON only: {"choice":"original|corrected|uncertain","confidence":0.0,"reason":"short reason"}. Do not expose chain-of-thought.';
  const r=await generate([{role:'system',content:system},{role:'user',content:JSON.stringify({task:input,task_contract:contract,original,corrected})}],webSearch,settings,{temperature:0.05,excludeProviders});
  if(!r)return null;const j=safeJson(r.text);if(!j)return null;
  const choice=['original','corrected','uncertain'].includes(j.choice)?j.choice:'uncertain';
  return {choice,confidence:clamp(j.confidence,0,1),reason:String(j.reason||''),provider:r.provider,model:r.model};
}

function ipHash(req){const raw=(req.headers.get('x-forwarded-for')||req.headers.get('x-real-ip')||'unknown').split(',')[0].trim();return createHash('sha256').update(`mus-ai|${raw}`).digest('hex').slice(0,32)}

export async function POST(req){
  const started=Date.now(),runId=randomUUID();
  try{
    const body=await req.json();const input=String(body.input||'').trim();
    if(!input)return NextResponse.json({message:'اكتب رسالة أولًا.'},{status:400});
    if(input.length>20000)return NextResponse.json({message:'الرسالة طويلة جدًا.'},{status:413});
    const sb=client();const {settings,lessons}=await loadRuntime(sb);
    if(settings.public_chat_enabled===false)return NextResponse.json({message:'MUS AI في وضع صيانة مؤقتًا.'},{status:503});

    const sessionId=isUuid(body.sessionId)?body.sessionId:randomUUID();const conversationId=isUuid(body.conversationId)?body.conversationId:randomUUID();const hash=ipHash(req);
    const quota=await sb.rpc('public_chat_allowed',{p_session_id:sessionId,p_ip_hash:hash});if(quota.error)throw quota.error;
    if(quota.data?.allowed===false){const msg=quota.data?.reason==='daily_limit'?'وصلت إلى الحد اليومي المجاني لهذه الجلسة.':'تم الوصول إلى الحد المؤقت للمحادثات. جرّب بعد قليل.';return NextResponse.json({message:msg},{status:429})}

    const contract=buildTaskContract(input);const maxCalls=clamp(settings?.max_model_calls_per_request??3,1,4);
    const requestedSearch=!!(body.webSearch||settings?.web_search_default);const paidSearchAllowed=!!settings?.allow_paid_external;
    const autoSearch=settings?.intelligence_router_enabled!==false&&contract.requires_web&&!!settings?.public_web_search_enabled&&paidSearchAllowed;
    const useSearch=paidSearchAllowed&&!!settings?.public_web_search_enabled&&(requestedSearch||autoSearch);
    const deep=settings?.intelligence_router_enabled!==false&&settings?.deep_reasoning_enabled!==false&&contract.difficulty==='hard'&&maxCalls>=3;
    const verify=settings?.verification_enabled!==false&&contract.requires_verification&&maxCalls>=2;
    const route={mode:deep?'deep':'standard',domain:contract.domain,difficulty:contract.difficulty,web_search:useSearch,verification:verify,independent_candidates:deep?2:1,max_model_calls:maxCalls,zero_cost_policy:!paidSearchAllowed};

    const lessonText=lessons.length?lessons.map((l,i)=>`${i+1}. ${l.title}: ${l.instruction}`).join('\n'):'لا توجد قواعد إضافية.';
    const system=`أنت MUS AI، مساعد ذكاء عام احترافي. افهم الطلب كعقد: حافظ على أسماء الكيانات والمهام والأرقام والاعتماديات كما كتبها المستخدم، ثم حل المطلوب. لا تختلق حقيقة أو مصدرًا أو تنفيذًا لم يحدث. إذا احتاجت المهمة معلومات حديثة ولم يتوفر بحث حالي فصرّح بعدم القدرة على تأكيد الحداثة. في الرياضيات راجع الحساب. في مسائل التخطيط حوّل النص أولًا داخليًا إلى: task_name, duration, dependencies, resources, objective ثم تحقق من أن التحويل يطابق النص قبل الحل. لا تعرض سلسلة تفكير خاصة.\n\nعقد المهمة:\n${JSON.stringify(contract)}\n\nقواعد MUS AI المعتمدة:\n${lessonText}`;
    const maxHistory=Math.max(4,Math.min(64,Number(settings?.max_history||16)));
    const history=Array.isArray(body.history)?body.history.slice(-maxHistory).filter(x=>['user','assistant'].includes(x?.role)&&typeof x?.content==='string').map(x=>({role:x.role,content:x.content.slice(0,14000)})):[];
    const baseMessages=[{role:'system',content:system},...history,{role:'user',content:input}];

    let modelCalls=0;const candidates=[];
    const first=await generate(baseMessages,useSearch,settings,{temperature:Number(settings?.temperature??0.6)});modelCalls++;
    if(!first)return NextResponse.json({message:'لا يوجد محرك مجاني متاح الآن.'},{status:503});
    candidates.push(first);

    if(deep&&modelCalls<maxCalls-1){
      const alt=[{role:'system',content:`${system}\n\nأنت مسار مستقل ثانٍ. لا تفترض أن الحل الأول صحيح. حل المهمة من الصفر بمنهج مختلف ثم أعط الجواب النهائي فقط.`},...history,{role:'user',content:input}];
      const second=await generate(alt,useSearch,settings,{temperature:0.35,excludeProviders:[first.provider]});modelCalls++;if(second)candidates.push(second);
    }

    let finalResult=candidates[0];
    let verification={verdict:contract.requires_verification?'unresolved':'pass',confidence:contract.requires_verification?0:0.78,issues:[],independent:false};
    if(verify&&modelCalls<maxCalls){
      verification=await verifyCandidate({input,contract,candidates,settings,webSearch:useSearch});modelCalls++;
      if(candidates.length>1&&verification.independent&&verification.confidence>=0.65&&verification.preferred){
        finalResult=candidates[verification.preferred==='B'?1:0]||candidates[0];
      }else if(candidates.length===1&&verification.independent&&verification.verdict==='repair'&&verification.corrected_answer&&modelCalls<maxCalls){
        const excluded=[candidates[0].provider,verification.verifier_provider].filter(Boolean);
        const adjudication=await adjudicateRepair({input,contract,original:candidates[0].text,corrected:verification.corrected_answer,settings,webSearch:useSearch,excludeProviders:excluded});modelCalls++;
        verification={...verification,adjudication};
        if(adjudication?.choice==='corrected'&&adjudication.confidence>=0.75){finalResult={...candidates[0],text:verification.corrected_answer,provider:adjudication.provider||candidates[0].provider,model:adjudication.model||candidates[0].model};verification.verdict='pass';verification.confidence=Math.min(verification.confidence,adjudication.confidence)}
        else if(adjudication?.choice==='original'&&adjudication.confidence>=0.75){verification.verdict='pass';verification.confidence=Math.min(verification.confidence,adjudication.confidence)}
        else verification.verdict='uncertain';
      }
    }

    if(contract.requires_web&&!useSearch)verification={...verification,verdict:'uncertain',confidence:Math.min(verification.confidence||0,0.30),issues:[...(verification.issues||[]),'No current/source web evidence available under zero-cost policy']};
    const minConfidence=Number(settings?.learning_gate_min_confidence??0.72);const evidenceReady=!contract.requires_web||(useSearch&&(finalResult.citations||[]).length>0);
    const learningEligible=verify&&verification.independent&&evidenceReady&&!contract.high_risk&&verification.verdict==='pass'&&Number(verification.confidence||0)>=minConfidence&&finalResult.text.length>=40;
    const latency=Date.now()-started;

    let logData=null;try{
      const logged=await sb.rpc('log_public_exchange_v2',{p_session_id:sessionId,p_conversation_id:conversationId,p_user_input:input,p_assistant_output:finalResult.text,p_provider:finalResult.provider,p_model:finalResult.model,p_web_search:useSearch,p_ip_hash:hash,p_run_id:runId,p_task_contract:contract,p_route_decision:{...route,source_count:(finalResult.citations||[]).length,candidate_providers:candidates.map(c=>c.provider)},p_verification:{verdict:verification.verdict,confidence:verification.confidence,issues:verification.issues||[],independent:!!verification.independent,verifier_provider:verification.verifier_provider||null,verifier_model:verification.verifier_model||null,adjudication:verification.adjudication||null},p_latency_ms:latency,p_model_calls:modelCalls,p_difficulty:contract.difficulty,p_learning_eligible:learningEligible});
      if(!logged.error)logData=logged.data;
    }catch{}

    return NextResponse.json({text:finalResult.text,provider:'mus-ai',model:'MUS AI',session_id:sessionId,conversation_id:conversationId,chat_log_id:logData?.chat_log_id||null,training_example_id:logData?.training_example_id||null,remaining:quota.data?.remaining??null,run_id:runId});
  }catch(e){return NextResponse.json({message:e?.message||'حدث خطأ في خدمة MUS AI.'},{status:500})}
}
