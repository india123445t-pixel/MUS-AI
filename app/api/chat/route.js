import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createHash, randomUUID } from 'crypto';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function client(){if(!SUPABASE_URL||!SUPABASE_KEY)throw new Error('Supabase environment is not configured.');return createClient(SUPABASE_URL,SUPABASE_KEY,{auth:{persistSession:false}})}
function isUuid(v=''){return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(v))}
function normalizeEndpoint(raw){if(!raw)return null;const url=raw.replace(/\/$/,'');if(url.endsWith('/chat/completions'))return url;if(url.endsWith('/v1'))return `${url}/chat/completions`;return url}
function clamp(n,min,max){return Math.max(min,Math.min(max,Number(n)||0))}
function safeJson(text){try{return JSON.parse(String(text||'').replace(/^```json\s*/i,'').replace(/```\s*$/,'').trim())}catch{}try{const s=String(text||'');const a=s.indexOf('{'),b=s.lastIndexOf('}');if(a>=0&&b>a)return JSON.parse(s.slice(a,b+1))}catch{}return null}
function includesAny(text,terms){return terms.some(t=>text.includes(t))}
function extractCitations(message){return (message?.annotations||[]).filter(a=>a?.type==='url_citation'&&a?.url_citation?.url).slice(0,8).map(a=>({url:String(a.url_citation.url),title:String(a.url_citation.title||''),content:String(a.url_citation.content||'').slice(0,1800)}))}

async function loadRuntime(sb){
  const [cfg,lessons]=await Promise.all([sb.rpc('get_mus_runtime_config'),sb.rpc('get_mus_runtime_lessons',{p_limit:18})]);
  return {settings:cfg.data||{},lessons:lessons.data||[]};
}

function buildTaskContract(input){
  const l=input.toLowerCase();
  const coding=includesAny(l,[' code','code ','bug','debug','typescript','javascript','python','react','next.js','sql','api','function','repository','github','برمج','كود','تصحيح خطأ','خطأ برمجي','مستودع','قاعدة بيانات','دالة']);
  const math=includesAny(l,['math','equation','calculate','proof','probability','algebra','geometry','رياضيات','معادلة','احسب','حساب','برهان','احتمال','نسبة مئوية']);
  const research=includesAny(l,['research','sources','source','citation','documentation','compare','benchmark','ابحث','بحث','مصادر','مصدر','قارن','مقارنة','وثائق','دراسة']);
  const planning=includesAny(l,['architecture','roadmap','strategy','plan ','planning','design system','معمارية','خطة','استراتيجية','صمم','تصميم نظام','خارطة طريق']);
  const freshness=includesAny(l,['latest','current','today','now','recent','price','weather','news','2026','اليوم','الآن','حالي','أحدث','آخر إصدار','سعر','طقس','أخبار']);
  const highRisk=includesAny(l,['diagnosis','dose','prescription','lawsuit','legal advice','investment advice','medical','تشخيص','جرعة','دواء','استشارة قانونية','قانوني','استثمار','طبي']);
  let domain='general';if(coding)domain='coding';else if(math)domain='math';else if(research)domain='research';else if(planning)domain='planning';
  let score=0;
  if(input.length>900)score++;
  if((input.match(/\n/g)||[]).length>=5)score++;
  if(coding||math||research||planning)score++;
  if(includesAny(l,['step by step','deep','complex','hard','optimize','production','security','دقيق','بعمق','معقد','احترافي','أقوى','أمان','إنتاجي']))score++;
  if((input.match(/[?؟]/g)||[]).length>=3)score++;
  const difficulty=score>=3?'hard':score>=1?'normal':'easy';
  return {
    domain,
    difficulty,
    language:/[\u0600-\u06ff]/.test(input)?'ar':'other',
    requires_web:freshness||research,
    freshness_required:freshness,
    requires_verification:coding||math||research||planning||highRisk,
    high_risk:highRisk,
    success_criteria:[
      'Answer the user request directly',
      'Do not invent facts, sources, executions, or tool results',
      ...(freshness?['Current claims must be supported by current evidence or explicitly marked unverified']:[]),
      ...(coding?['Code claims must not be described as executed unless actually executed']:[]),
      ...(math?['Recheck calculations and constraints before finalizing']:[])
    ]
  };
}

async function selfHosted(messages,settings,opts={}){
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

async function groq(messages,settings,opts={}){
  return openAICompatible({key:process.env.GROQ_API_KEY,url:'https://api.groq.com/openai/v1/chat/completions',model:process.env.GROQ_MODEL||'openai/gpt-oss-120b',provider:'groq',messages,temperature:Number(opts.temperature??settings?.temperature??0.6),payloadExtra:{reasoning_effort:opts.temperature!=null&&Number(opts.temperature)<=0.15?'low':'medium'}});
}

async function mistral(messages,settings,opts={}){
  return openAICompatible({key:process.env.MISTRAL_API_KEY,url:'https://api.mistral.ai/v1/chat/completions',model:process.env.MISTRAL_MODEL||'mistral-small-latest',provider:'mistral',messages,temperature:Number(opts.temperature??settings?.temperature??0.6)});
}

async function cerebras(messages,settings,opts={}){
  return openAICompatible({key:process.env.CEREBRAS_API_KEY,url:'https://api.cerebras.ai/v1/chat/completions',model:process.env.CEREBRAS_MODEL||'gpt-oss-120b',provider:'cerebras',messages,temperature:Number(opts.temperature??settings?.temperature??0.6),headers:{'X-Cerebras-Version-Patch':'2'}});
}

async function huggingFace(messages,settings,opts={}){
  if(process.env.HF_FREE_FALLBACK_ENABLED!=='true')return null;
  return openAICompatible({key:process.env.HF_TOKEN,url:'https://router.huggingface.co/v1/chat/completions',model:process.env.HF_MODEL||'openai/gpt-oss-120b:cheapest',provider:'huggingface',messages,temperature:Number(opts.temperature??settings?.temperature??0.6)});
}

async function gemini(messages,settings,opts={}){
  const key=process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY;if(!key)return null;
  try{
    const model=process.env.GEMINI_MODEL||'gemini-3.8-flash';
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
  const providers=[
    ()=>openRouter(messages,webSearch,settings,opts),
    ()=>groq(messages,settings,opts),
    ()=>gemini(messages,settings,opts),
    ()=>mistral(messages,settings,opts),
    ()=>cerebras(messages,settings,opts),
    ()=>huggingFace(messages,settings,opts)
  ];
  for(const run of providers){try{const r=await run();if(r)return r}catch{}}
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
  let verdict=String(raw.verdict||'unresolved').toLowerCase();
  if(!['pass','repair','uncertain','unresolved'].includes(verdict))verdict='unresolved';
  return {verdict,confidence:clamp(raw.confidence,0,1),issues:Array.isArray(raw.issues)?raw.issues.slice(0,6).map(String):[],corrected_answer:typeof raw.corrected_answer==='string'?raw.corrected_answer.trim():'',preferred:raw.preferred||null};
}

async function verifyCandidate({input,contract,candidates,settings,webSearch}){
  if(contract.requires_web&&!webSearch)return {verdict:'uncertain',confidence:0.30,issues:['The task needs current/source evidence but web evidence is unavailable under the current zero-cost policy.']};
  const multi=candidates.length>1;
  const verifierSystem=`You are the MUS AI verification layer. Judge correctness, constraint satisfaction, factual support and whether the answer actually fulfills the task. For mathematics solve independently where practical. For code, review for likely correctness but NEVER claim execution unless execution evidence exists. For research/current facts, reject unsupported current claims; supplied citation snippets are evidence only when they actually support the claim. Do not reveal chain-of-thought. Return STRICT JSON only with this schema: {"verdict":"pass|repair|uncertain","confidence":0.0,"issues":["short issue"],"preferred":"A|B|null","corrected_answer":"final answer only if repair is needed or if selecting/merging candidates materially improves correctness"}.`;
  const payload={task:input,task_contract:contract,candidates:candidates.map((c,i)=>({label:String.fromCharCode(65+i),answer:c.text,citations:c.citations||[]}))};
  const r=await generate([{role:'system',content:verifierSystem},{role:'user',content:JSON.stringify(payload)}],webSearch,settings,{temperature:0.1});
  if(!r)return {verdict:'unresolved',confidence:0,issues:['Verifier unavailable']};
  const v=normalizeVerification(safeJson(r.text));
  let finalText='';
  if(v.corrected_answer)finalText=v.corrected_answer;
  else if(multi&&['A','B'].includes(v.preferred))finalText=candidates[v.preferred==='A'?0:1]?.text||'';
  return {...v,finalText,verifier_provider:r.provider,verifier_model:r.model};
}

function ipHash(req){const raw=(req.headers.get('x-forwarded-for')||req.headers.get('x-real-ip')||'unknown').split(',')[0].trim();return createHash('sha256').update(`mus-ai|${raw}`).digest('hex').slice(0,32)}

export async function POST(req){
  const started=Date.now();
  const runId=randomUUID();
  try{
    const body=await req.json();
    const input=String(body.input||'').trim();if(!input)return NextResponse.json({message:'اكتب رسالة أولًا.'},{status:400});
    if(input.length>20000)return NextResponse.json({message:'الرسالة طويلة جدًا.'},{status:413});

    const sb=client();const {settings,lessons}=await loadRuntime(sb);
    if(settings.public_chat_enabled===false)return NextResponse.json({message:'MUS AI في وضع صيانة مؤقتًا.'},{status:503});

    const sessionId=isUuid(body.sessionId)?body.sessionId:randomUUID();
    const conversationId=isUuid(body.conversationId)?body.conversationId:randomUUID();
    const hash=ipHash(req);
    const quota=await sb.rpc('public_chat_allowed',{p_session_id:sessionId,p_ip_hash:hash});
    if(quota.error)throw quota.error;
    if(quota.data?.allowed===false){const msg=quota.data?.reason==='daily_limit'?'وصلت إلى الحد اليومي المجاني لهذه الجلسة.':'تم الوصول إلى الحد المؤقت للمحادثات. جرّب بعد قليل.';return NextResponse.json({message:msg},{status:429})}

    const contract=buildTaskContract(input);
    const maxCalls=clamp(settings?.max_model_calls_per_request??3,1,4);
    const requestedSearch=!!(body.webSearch||settings?.web_search_default);
    const paidSearchAllowed=!!settings?.allow_paid_external;
    const autoSearch=settings?.intelligence_router_enabled!==false&&contract.requires_web&&!!settings?.public_web_search_enabled&&paidSearchAllowed;
    const useSearch=paidSearchAllowed&&!!settings?.public_web_search_enabled&&(requestedSearch||autoSearch);
    const deep=settings?.intelligence_router_enabled!==false&&settings?.deep_reasoning_enabled!==false&&contract.difficulty==='hard'&&maxCalls>=3;
    const verify=settings?.verification_enabled!==false&&contract.requires_verification&&maxCalls>=(deep?3:2);
    const route={mode:deep?'deep':'standard',domain:contract.domain,difficulty:contract.difficulty,web_search:useSearch,verification:verify,independent_candidates:deep?2:1,max_model_calls:maxCalls,zero_cost_policy:!paidSearchAllowed};

    const lessonText=lessons.length?lessons.map((l,i)=>`${i+1}. ${l.title}: ${l.instruction}`).join('\n'):'لا توجد قواعد إضافية.';
    const system=`أنت MUS AI، مساعد ذكاء عام احترافي. هدفك تقديم أفضل جواب صحيح وقابل للتحقق بأقل خطوات لازمة. افهم هدف المستخدم والقيود، ولا تختلق حقيقة أو مصدرًا أو تنفيذًا لم يحدث. إذا كانت المهمة تحتاج معلومات حديثة أو مصادر ولم يتوفر بحث حالي، فقل بوضوح إنك لا تستطيع تأكيد الحداثة أو المصدر الآن بدل اختلاقه. في البرمجة لا تقل إن الكود تم تشغيله أو اختباره ما لم توجد نتيجة تنفيذ فعلية. في الرياضيات راجع الحساب والقيود. لا تذكر مزود النموذج للمستخدم؛ هويتك MUS AI. فكّر داخليًا ولا تعرض سلسلة تفكير خاصة، بل أعط النتيجة والشرح المفيد فقط.\n\nعقد المهمة:\n${JSON.stringify(contract)}\n\nقواعد MUS AI المعتمدة:\n${lessonText}`;
    const maxHistory=Math.max(4,Math.min(64,Number(settings?.max_history||16)));
    const history=Array.isArray(body.history)?body.history.slice(-maxHistory).filter(x=>['user','assistant'].includes(x?.role)&&typeof x?.content==='string').map(x=>({role:x.role,content:x.content.slice(0,14000)})):[];
    const baseMessages=[{role:'system',content:system},...history,{role:'user',content:input}];

    let modelCalls=0;
    const candidates=[];
    const first=await generate(baseMessages,useSearch,settings,{temperature:Number(settings?.temperature??0.6)});modelCalls++;
    if(!first)return NextResponse.json({message:'لا يوجد محرك مجاني متاح الآن. أضف أحد مفاتيح Gemini أو Groq أو Mistral أو Cerebras إلى إعدادات الخادم.'},{status:503});
    candidates.push(first);

    if(deep&&modelCalls<maxCalls-1){
      const altMessages=[{role:'system',content:`${system}\n\nأنت الآن مسار مستقل ثانٍ. لا تفترض أن أي حل سابق صحيح. حاول منهجًا مختلفًا إذا كان ذلك مفيدًا، ثم أعط جوابك النهائي فقط.`},...history,{role:'user',content:input}];
      try{const second=await generate(altMessages,useSearch,settings,{temperature:0.35});modelCalls++;if(second)candidates.push(second)}catch{}
    }

    let verification={verdict:contract.requires_verification?'unresolved':'pass',confidence:contract.requires_verification?0:0.78,issues:[]};
    let finalResult=candidates[0];
    if(verify&&modelCalls<maxCalls){
      try{
        verification=await verifyCandidate({input,contract,candidates,settings,webSearch:useSearch});modelCalls++;
        if(verification.finalText){
          const preferredIndex=verification.preferred==='B'&&candidates[1]?1:0;
          finalResult={...candidates[preferredIndex],text:verification.finalText};
        }else if(verification.preferred==='B'&&candidates[1])finalResult=candidates[1];
      }catch(e){verification={verdict:'unresolved',confidence:0,issues:['Verification failed safely']}}
    }

    if(contract.requires_web&&!useSearch){verification={...verification,verdict:'uncertain',confidence:Math.min(verification.confidence||0,0.30),issues:[...(verification.issues||[]),'No current/source web evidence available under zero-cost policy']}}

    const minConfidence=Number(settings?.learning_gate_min_confidence??0.72);
    const evidenceReady=!contract.requires_web||(useSearch&&(finalResult.citations||[]).length>0);
    const learningEligible=verify&&evidenceReady&&!contract.high_risk&&verification.verdict==='pass'&&Number(verification.confidence||0)>=minConfidence&&finalResult.text.length>=40;
    const latency=Date.now()-started;

    let logData=null;
    try{
      const logged=await sb.rpc('log_public_exchange_v2',{
        p_session_id:sessionId,p_conversation_id:conversationId,p_user_input:input,p_assistant_output:finalResult.text,
        p_provider:finalResult.provider,p_model:finalResult.model,p_web_search:useSearch,p_ip_hash:hash,p_run_id:runId,
        p_task_contract:contract,p_route_decision:{...route,source_count:(finalResult.citations||[]).length},p_verification:{verdict:verification.verdict,confidence:verification.confidence,issues:verification.issues||[],verifier_provider:verification.verifier_provider||null,verifier_model:verification.verifier_model||null},
        p_latency_ms:latency,p_model_calls:modelCalls,p_difficulty:contract.difficulty,p_learning_eligible:learningEligible
      });
      if(!logged.error)logData=logged.data;
    }catch{}

    return NextResponse.json({text:finalResult.text,provider:'mus-ai',model:'MUS AI',session_id:sessionId,conversation_id:conversationId,chat_log_id:logData?.chat_log_id||null,training_example_id:logData?.training_example_id||null,remaining:quota.data?.remaining??null,run_id:runId});
  }catch(e){return NextResponse.json({message:e?.message||'حدث خطأ في خدمة MUS AI.'},{status:500})}
}
