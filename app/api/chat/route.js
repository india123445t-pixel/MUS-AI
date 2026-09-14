import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createHash, randomUUID } from 'crypto';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function client(){if(!SUPABASE_URL||!SUPABASE_KEY)throw new Error('Supabase environment is not configured.');return createClient(SUPABASE_URL,SUPABASE_KEY,{auth:{persistSession:false}})}
function isUuid(v=''){return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(v))}
function normalizeEndpoint(raw){if(!raw)return null;const url=raw.replace(/\/$/,'');if(url.endsWith('/chat/completions'))return url;if(url.endsWith('/v1'))return `${url}/chat/completions`;return url}

async function loadRuntime(sb){
  const [cfg,lessons]=await Promise.all([sb.rpc('get_mus_runtime_config'),sb.rpc('get_mus_runtime_lessons',{p_limit:18})]);
  return {settings:cfg.data||{},lessons:lessons.data||[]};
}
async function selfHosted(messages,settings){
  const endpoint=normalizeEndpoint(process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL);if(!endpoint)return null;
  try{
    const key=process.env.MUS_MODEL_KEY||process.env.LOCAL_MODEL_KEY;
    const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json',...(key?{Authorization:`Bearer ${key}`}:{})},body:JSON.stringify({model:settings?.self_hosted_model||process.env.MUS_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'mus-ai',messages,temperature:Number(settings?.temperature??0.6),stream:false}),signal:AbortSignal.timeout(65000)});
    if(!r.ok)return null;const d=await r.json();const text=d?.choices?.[0]?.message?.content||d?.message?.content||d?.response||null;
    return text?{text,provider:'mus-engine',model:d?.model||settings?.self_hosted_model||'MUS AI'}:null;
  }catch{return null}
}
async function openRouter(messages,webSearch,settings){
  const key=process.env.OPENROUTER_API_KEY;if(!key)return null;
  let model=settings?.openrouter_model||process.env.OPENROUTER_MODEL||'openrouter/free';
  if(!settings?.allow_paid_external&&!String(model).includes(':free')&&model!=='openrouter/free')model='openrouter/free';
  const payload={model,messages,temperature:Number(settings?.temperature??0.6)};
  if(webSearch&&settings?.public_web_search_enabled)payload.plugins=[{id:'web',max_results:4}];
  const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{method:'POST',headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json','X-Title':'MUS AI'},body:JSON.stringify(payload),signal:AbortSignal.timeout(75000)});
  const d=await r.json();if(!r.ok)throw new Error(d?.error?.message||'تعذر الوصول إلى محرك MUS AI الآن.');
  return {text:d?.choices?.[0]?.message?.content||'لم يصل رد من النموذج.',provider:'openrouter',model:d?.model||model};
}
function ipHash(req){const raw=(req.headers.get('x-forwarded-for')||req.headers.get('x-real-ip')||'unknown').split(',')[0].trim();return createHash('sha256').update(`mus-ai|${raw}`).digest('hex').slice(0,32)}

export async function POST(req){
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

    const lessonText=lessons.length?lessons.map((l,i)=>`${i+1}. ${l.title}: ${l.instruction}`).join('\n'):'لا توجد قواعد إضافية.';
    const system=`أنت MUS AI، مساعد ذكاء عام احترافي يتطور باستمرار. كن مفيدًا ودقيقًا ومباشرًا. افهم هدف المستخدم قبل الإجابة، لا تختلق حقائق أو مصادر أو تنفيذًا لم يحدث، ميّز بين الحقيقة والاحتمال، واستخدم الأدلة والبحث عند توفره. لا تذكر مزود النموذج للمستخدم ولا تصف نفسك كنموذج خارجي؛ هويتك أمام المستخدم هي MUS AI.\n\nقواعد MUS AI المعتمدة:\n${lessonText}`;
    const maxHistory=Math.max(4,Math.min(64,Number(settings?.max_history||16)));
    const history=Array.isArray(body.history)?body.history.slice(-maxHistory).filter(x=>['user','assistant'].includes(x?.role)&&typeof x?.content==='string').map(x=>({role:x.role,content:x.content.slice(0,14000)})):[];
    const messages=[{role:'system',content:system},...history,{role:'user',content:input}];
    const requestedSearch=!!body.webSearch&&!!settings?.public_web_search_enabled;
    const mode=settings?.runtime_mode||'openrouter_primary';
    let result=null;
    if(mode==='openrouter_primary'||mode==='openrouter_only'){
      result=await openRouter(messages,requestedSearch,settings);
      if(!result&&mode!=='openrouter_only')result=await selfHosted(messages,settings);
    }else{
      result=await selfHosted(messages,settings);
      if(!result&&mode!=='self_hosted_only')result=await openRouter(messages,requestedSearch,settings);
    }
    if(!result)return NextResponse.json({message:'لا يوجد محرك متاح الآن.'},{status:503});

    let logData=null;
    try{
      const logged=await sb.rpc('log_public_exchange',{p_session_id:sessionId,p_conversation_id:conversationId,p_user_input:input,p_assistant_output:result.text,p_provider:result.provider,p_model:result.model,p_web_search:requestedSearch,p_ip_hash:hash});
      if(!logged.error)logData=logged.data;
    }catch{}

    return NextResponse.json({text:result.text,provider:'mus-ai',model:'MUS AI',session_id:sessionId,conversation_id:conversationId,chat_log_id:logData?.chat_log_id||null,training_example_id:logData?.training_example_id||null,remaining:quota.data?.remaining??null});
  }catch(e){return NextResponse.json({message:e?.message||'حدث خطأ في خدمة MUS AI.'},{status:500})}
}
