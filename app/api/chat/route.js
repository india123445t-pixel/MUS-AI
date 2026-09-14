import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
function authedClient(token){if(!SUPABASE_URL||!SUPABASE_KEY)throw new Error('Supabase environment is not configured.');return createClient(SUPABASE_URL,SUPABASE_KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}})}
function words(s=''){return String(s).toLowerCase().split(/[^\p{L}\p{N}_-]+/u).filter(x=>x.length>2)}
function scoreText(text,queryWords){const t=String(text||'').toLowerCase();return queryWords.reduce((n,w)=>n+(t.includes(w)?1:0),0)}

async function contextAndSettings(token,input){
  if(!token)return {lessons:[],memories:[],settings:null};const sb=authedClient(token),q=words(input);
  const [lr,mr,sr]=await Promise.all([
    sb.from('lessons').select('title,instruction,priority,status').eq('status','approved').order('priority',{ascending:false}).limit(70),
    sb.from('memories').select('content,enabled').eq('enabled',true).order('updated_at',{ascending:false}).limit(70),
    sb.from('control_settings').select('*').maybeSingle()
  ]);
  const lessons=(lr.data||[]).map(x=>({...x,score:scoreText(`${x.title} ${x.instruction}`,q)})).sort((a,b)=>b.score-a.score||b.priority-a.priority).slice(0,10);
  const memories=(mr.data||[]).map(x=>({...x,score:scoreText(x.content,q)})).sort((a,b)=>b.score-a.score).slice(0,10);
  return {lessons,memories,settings:sr.data||null};
}
function normalizeEndpoint(raw){if(!raw)return null;const url=raw.replace(/\/$/,'');if(url.endsWith('/chat/completions'))return url;if(url.endsWith('/v1'))return `${url}/chat/completions`;return url}
async function selfHosted(messages,settings){const endpoint=normalizeEndpoint(process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL);if(!endpoint)return null;try{const key=process.env.MUS_MODEL_KEY||process.env.LOCAL_MODEL_KEY;const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json',...(key?{Authorization:`Bearer ${key}`}:{})},body:JSON.stringify({model:settings?.self_hosted_model||process.env.MUS_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'mus-ai',messages,temperature:Number(settings?.temperature??0.6),stream:false}),signal:AbortSignal.timeout(60000)});if(!r.ok)return null;const d=await r.json();const text=d?.choices?.[0]?.message?.content||d?.message?.content||d?.response||null;return text?{text,provider:'mus-engine',model:d?.model||settings?.self_hosted_model||'MUS AI'}:null}catch{return null}}
async function openRouter(messages,webSearch,settings){const key=process.env.OPENROUTER_API_KEY;if(!key)return null;let model=settings?.openrouter_model||process.env.OPENROUTER_MODEL||'openrouter/free';const allowsPaid=!!settings?.allow_paid_external;if(!allowsPaid&&!String(model).includes(':free')&&model!=='openrouter/free')model='openrouter/free';const payload={model,messages,temperature:Number(settings?.temperature??0.6)};if(webSearch)payload.plugins=[{id:'web',max_results:4}];const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{method:'POST',headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json','X-Title':'MUS AI'},body:JSON.stringify(payload),signal:AbortSignal.timeout(75000)});const d=await r.json();if(!r.ok)throw new Error(d?.error?.message||'فشل OpenRouter.');return {text:d?.choices?.[0]?.message?.content||'لم يصل رد من النموذج.',provider:'openrouter',model:d?.model||model}}

export async function POST(req){
  try{
    const body=await req.json(),input=String(body.input||'').trim();if(!input)return NextResponse.json({message:'اكتب رسالة أولًا.'},{status:400});
    const auth=req.headers.get('authorization')||'',token=auth.startsWith('Bearer ')?auth.slice(7):'';const {lessons,memories,settings}=await contextAndSettings(token,input);
    const lessonText=lessons.length?lessons.map((l,i)=>`${i+1}. ${l.title}: ${l.instruction}`).join('\n'):'لا توجد دروس مرتبطة.';
    const memoryText=memories.length?memories.map((m,i)=>`${i+1}. ${m.content}`).join('\n'):'لا توجد ذكريات مرتبطة.';
    const system=`أنت MUS AI، مساعد ذكاء عام يتطور باستمرار. هدفك أعلى جودة موثوقة بأقل تكلفة. افهم طلب المستخدم بدقة، استخدم الأدلة، لا تدّعي تنفيذ شيء لم يحدث، لا تخترع مصادر أو نتائج، وميّز بين الحقيقة والاحتمال. استخدم الذاكرة والدروس فقط عندما تكون ذات صلة. ${settings?.system_note||''}\n\nالدروس ذات الصلة:\n${lessonText}\n\nالذكريات ذات الصلة:\n${memoryText}`;
    const maxHistory=Math.max(4,Math.min(64,Number(settings?.max_history||16)));const history=Array.isArray(body.history)?body.history.slice(-maxHistory).filter(x=>['user','assistant'].includes(x?.role)&&typeof x?.content==='string').map(x=>({role:x.role,content:x.content.slice(0,14000)})):[];
    const messages=[{role:'system',content:system},...history,{role:'user',content:input}],mode=settings?.runtime_mode||'openrouter_primary',webSearch=body.webSearch??settings?.web_search_default??false;
    if(mode==='openrouter_primary'||mode==='openrouter_only'){const remote=await openRouter(messages,!!webSearch,settings);if(remote)return NextResponse.json(remote);if(mode==='openrouter_only')return NextResponse.json({message:'OpenRouter غير متصل.'},{status:503});const local=await selfHosted(messages,settings);if(local)return NextResponse.json(local)}
    else {const local=await selfHosted(messages,settings);if(local)return NextResponse.json(local);if(mode==='self_hosted_only')return NextResponse.json({message:'محرك MUS AI الذاتي غير متصل بعد.'},{status:503});const remote=await openRouter(messages,!!webSearch,settings);if(remote)return NextResponse.json(remote)}
    return NextResponse.json({message:'لا يوجد محرك متاح الآن.'},{status:503});
  }catch(e){return NextResponse.json({message:e?.message||'حدث خطأ في خدمة الدردشة.'},{status:500})}
}
