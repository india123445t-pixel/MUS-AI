import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function client(token){
  if(!SUPABASE_URL||!SUPABASE_KEY)throw new Error('Supabase environment is not configured.');
  return createClient(SUPABASE_URL,SUPABASE_KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}});
}
function normalizeEndpoint(raw){if(!raw)return null;const url=raw.replace(/\/$/,'');if(url.endsWith('/chat/completions'))return url;if(url.endsWith('/v1'))return `${url}/chat/completions`;return url}
async function localCall(messages){
  const endpoint=normalizeEndpoint(process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL);if(!endpoint)return null;
  try{
    const key=process.env.MUS_MODEL_KEY||process.env.LOCAL_MODEL_KEY;
    const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json',...(key?{Authorization:`Bearer ${key}`}:{})},body:JSON.stringify({model:process.env.MUS_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'mus-ai',messages,temperature:0.4,stream:false}),signal:AbortSignal.timeout(60000)});
    if(!r.ok)return null;const d=await r.json();const text=d?.choices?.[0]?.message?.content||d?.message?.content||d?.response||null;return text?{text,provider:'self-hosted',model:d?.model||process.env.MUS_MODEL_NAME||'mus-ai'}:null;
  }catch{return null}
}
async function freeTeacher(messages){
  const key=process.env.OPENROUTER_API_KEY;if(!key)return null;
  try{
    const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{method:'POST',headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json','X-Title':'MUS AI Goal Engine'},body:JSON.stringify({model:process.env.MUS_AUTONOMOUS_MODEL||'openrouter/free',messages,temperature:0.35}),signal:AbortSignal.timeout(60000)});
    const d=await r.json();if(!r.ok)return null;const text=d?.choices?.[0]?.message?.content||null;return text?{text,provider:'openrouter-free',model:d?.model||'openrouter/free'}:null;
  }catch{return null}
}
async function teacher(messages){return await freeTeacher(messages)||await localCall(messages)}
function parseVerifier(raw=''){
  const match=String(raw).match(/\{[\s\S]*\}/);if(match){try{const j=JSON.parse(match[0]);return{score:Math.max(0,Math.min(100,Number(j.score)||0)),critique:String(j.critique||''),preferred:String(j.preferred_answer||'')}}catch{}}
  const n=String(raw).match(/(?:score|النتيجة)\s*[:=]?\s*(\d{1,3})/i);return{score:Math.max(0,Math.min(100,Number(n?.[1])||0)),critique:String(raw).slice(0,4000),preferred:''};
}
export async function POST(req){
  try{
    const auth=req.headers.get('authorization')||'',token=auth.startsWith('Bearer ')?auth.slice(7):'';if(!token)return NextResponse.json({message:'يلزم تسجيل الدخول.'},{status:401});
    const sb=client(token),userRes=await sb.auth.getUser(),u=userRes.data?.user;if(!u)return NextResponse.json({message:'جلسة غير صالحة.'},{status:401});
    const goalRes=await sb.from('goals').select('*').eq('status','active').order('priority',{ascending:false}).limit(1).maybeSingle(),goal=goalRes.data;if(!goal)return NextResponse.json({message:'لا يوجد هدف نشط لـ MUS AI.'},{status:404});
    const skillsRes=await sb.from('skill_state').select('domain,score,attempts,wins').order('score',{ascending:true}).order('attempts',{ascending:true}).limit(8),skills=skillsRes.data||[],target=skills[0]||{domain:'reasoning',score:0,attempts:0,wins:0},domain=target.domain;
    const challengeResult=await teacher([{role:'system',content:'أنت مُعلّم صارم لنموذج ذكاء عام. أنشئ سؤالًا واحدًا صعبًا لكنه قابل للتحقق موضوعيًا. لا تعطِ الحل ولا شرحًا.'},{role:'user',content:`المجال: ${domain}. الهدف: ${goal.objective}. أنشئ اختبارًا واحدًا يقيس الفهم الحقيقي والاستدلال، وليس الحفظ السطحي.`}]);
    if(!challengeResult)return NextResponse.json({message:'لا يوجد محرك مجاني متاح الآن لإنشاء دورة التعلم. لم يتم استخدام أي مورد مدفوع.'},{status:503});
    const challenge=challengeResult.text.trim().slice(0,12000),coreSystem='أنت MUS AI. حل المهمة بأعلى دقة ممكنة. لا تختلق حقائق، واذكر عدم اليقين عند الحاجة. أعطِ الجواب النهائي مع تبرير موجز يمكن التحقق منه.';
    const studentResult=await localCall([{role:'system',content:coreSystem},{role:'user',content:challenge}])||await freeTeacher([{role:'system',content:coreSystem},{role:'user',content:challenge}]);
    if(!studentResult)return NextResponse.json({message:'تعذر تشغيل الطالب، ولم يتم اللجوء إلى مورد مدفوع.'},{status:503});
    const verifyResult=await teacher([{role:'system',content:'أنت Verifier مستقل وصارم. قيّم صحة الإجابة لا أسلوبها. أعد JSON فقط بالشكل {"score":0-100,"critique":"...","preferred_answer":"أفضل جواب صحيح مختصر"}. لا ترفع النتيجة لمجرد أن الإجابة تبدو واثقة.'},{role:'user',content:`المجال: ${domain}\nالمهمة:\n${challenge}\n\nإجابة MUS AI:\n${studentResult.text}`}]);
    if(!verifyResult)return NextResponse.json({message:'تعذر تشغيل المقيّم المجاني. لم يتم اعتماد أي تعلم.'},{status:503});
    const verdict=parseVerifier(verifyResult.text),old=Number(target.score)||0,next=target.attempts>0?(old*0.7+verdict.score*0.3):verdict.score,wins=(Number(target.wins)||0)+(verdict.score>=85?1:0),attempts=(Number(target.attempts)||0)+1;
    await sb.from('goal_runs').insert({owner_id:u.id,goal_id:goal.id,domain,task:challenge,answer:studentResult.text,verifier_notes:verdict.critique,score:verdict.score,cost_usd:0,provider:studentResult.provider,model:studentResult.model,outcome:verdict.score>=85?'pass':'learn'});
    await sb.from('skill_state').upsert({owner_id:u.id,domain,score:Number(next.toFixed(2)),attempts,wins,updated_at:new Date().toISOString()},{onConflict:'owner_id,domain'});
    await sb.from('training_examples').insert({owner_id:u.id,user_input:challenge,assistant_bad_answer:verdict.score<85?studentResult.text:null,preferred_answer:verdict.preferred||studentResult.text,category:domain,tags:['goal-engine',verdict.score>=85?'pass':'weakness'],quality_status:'candidate',context_snapshot:{goal_id:goal.id,score:verdict.score,critique:verdict.critique,student_provider:studentResult.provider,student_model:studentResult.model,verifier_provider:verifyResult.provider,verifier_model:verifyResult.model,cost_usd:0}});
    return NextResponse.json({ok:true,goal:goal.name,domain,task:challenge,answer:studentResult.text,score:verdict.score,critique:verdict.critique,preferred_answer:verdict.preferred,new_skill_score:Number(next.toFixed(2)),cost_usd:0,provider:studentResult.provider,model:studentResult.model});
  }catch(e){return NextResponse.json({message:e?.message||'فشلت دورة التعلم.'},{status:500})}
}
