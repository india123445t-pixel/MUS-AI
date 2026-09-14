import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function authedClient(token){
  if(!SUPABASE_URL||!SUPABASE_KEY)throw new Error('Supabase environment is not configured.');
  return createClient(SUPABASE_URL,SUPABASE_KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}});
}
function words(s=''){return String(s).toLowerCase().split(/[^\p{L}\p{N}_-]+/u).filter(x=>x.length>2)}
function scoreText(text,queryWords){const t=String(text||'').toLowerCase();return queryWords.reduce((n,w)=>n+(t.includes(w)?1:0),0)}
async function relevantContext(token,input){
  if(!token)return {lessons:[],memories:[]};
  const sb=authedClient(token),q=words(input);
  const [lr,mr]=await Promise.all([
    sb.from('lessons').select('title,instruction,priority,status').eq('status','approved').order('priority',{ascending:false}).limit(60),
    sb.from('memories').select('content,enabled').eq('enabled',true).order('updated_at',{ascending:false}).limit(60)
  ]);
  const lessons=(lr.data||[]).map(x=>({...x,score:scoreText(`${x.title} ${x.instruction}`,q)})).sort((a,b)=>b.score-a.score||b.priority-a.priority).slice(0,10);
  const memories=(mr.data||[]).map(x=>({...x,score:scoreText(x.content,q)})).sort((a,b)=>b.score-a.score).slice(0,10);
  return {lessons,memories};
}
function normalizeEndpoint(raw){if(!raw)return null;const url=raw.replace(/\/$/,'');if(url.endsWith('/chat/completions'))return url;if(url.endsWith('/v1'))return `${url}/chat/completions`;return url}
async function selfHosted(messages){
  const endpoint=normalizeEndpoint(process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL);if(!endpoint)return null;
  try{
    const key=process.env.MUS_MODEL_KEY||process.env.LOCAL_MODEL_KEY;
    const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json',...(key?{Authorization:`Bearer ${key}`}:{})},body:JSON.stringify({model:process.env.MUS_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'mus-ai',messages,temperature:0.6,stream:false}),signal:AbortSignal.timeout(45000)});
    if(!r.ok)return null;const d=await r.json();const text=d?.choices?.[0]?.message?.content||d?.message?.content||d?.response||null;return text?{text,provider:'self-hosted',model:d?.model||process.env.MUS_MODEL_NAME||'self-hosted'}:null;
  }catch{return null}
}
async function openRouter(messages,webSearch){
  const key=process.env.OPENROUTER_API_KEY;if(!key)return null;const model=process.env.OPENROUTER_MODEL||'openrouter/free';const payload={model,messages};if(webSearch)payload.plugins=[{id:'web',max_results:3}];
  const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{method:'POST',headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json','X-Title':'MUS AI'},body:JSON.stringify(payload),signal:AbortSignal.timeout(60000)});
  const d=await r.json();if(!r.ok)throw new Error(d?.error?.message||'فشل OpenRouter.');return {text:d?.choices?.[0]?.message?.content||'لم يصل رد من النموذج.',provider:'openrouter',model:d?.model||model};
}
export async function POST(req){
  try{
    const body=await req.json(),input=String(body.input||'').trim();if(!input)return NextResponse.json({message:'اكتب رسالة أولًا.'},{status:400});
    const auth=req.headers.get('authorization')||'',token=auth.startsWith('Bearer ')?auth.slice(7):'';const {lessons,memories}=await relevantContext(token,input);
    const lessonText=lessons.length?lessons.map((l,i)=>`${i+1}. ${l.title}: ${l.instruction}`).join('\n'):'لا توجد دروس مرتبطة.';
    const memoryText=memories.length?memories.map((m,i)=>`${i+1}. ${m.content}`).join('\n'):'لا توجد ذكريات مرتبطة.';
    const system=`أنت MUS AI Living Core، نواة ذكاء عامة تتطور باستمرار. لست مساعد برمجة فقط.\nقواعدك: افهم الهدف، استخدم الأدلة، لا تخترع تنفيذًا لم يحدث، افصل الحقيقة عن الاحتمال، واستخدم الذاكرة فقط عندما تكون ذات صلة.\n\nالدروس ذات الصلة:\n${lessonText}\n\nالذكريات ذات الصلة:\n${memoryText}`;
    const history=Array.isArray(body.history)?body.history.slice(-12).filter(x=>['user','assistant'].includes(x?.role)&&typeof x?.content==='string').map(x=>({role:x.role,content:x.content.slice(0,12000)})):[];
    const messages=[{role:'system',content:system},...history,{role:'user',content:input}];
    const local=await selfHosted(messages);if(local)return NextResponse.json(local);
    if(!body.allowFallback)return NextResponse.json({message:'محرك MUS AI الذاتي غير موصول بعد. فعّل OpenRouter مؤقتًا أو أضف MUS_MODEL_URL.'},{status:503});
    const remote=await openRouter(messages,!!body.webSearch);if(!remote)return NextResponse.json({message:'لا يوجد محرك MUS AI ذاتي ولا مفتاح OpenRouter متاح.'},{status:503});return NextResponse.json(remote);
  }catch(e){return NextResponse.json({message:e?.message||'حدث خطأ في خدمة الدردشة.'},{status:500})}
}
