import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { randomUUID } from 'crypto';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL,KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
function client(token){if(!URL||!KEY)throw new Error('Supabase environment is not configured.');return createClient(URL,KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}})}
function parseFinalInteger(text=''){const m=String(text).match(/(?:^|\n)\s*FINAL\s*[:=]\s*(-?\d+)\s*(?:$|\n)/i);return m?Number(m[1]):null}

export async function POST(req){
 try{
  const auth=req.headers.get('authorization')||'',token=auth.startsWith('Bearer ')?auth.slice(7):'';
  if(!token)return NextResponse.json({message:'يلزم تسجيل الدخول.'},{status:401});
  const sb=client(token),ur=await sb.auth.getUser(),u=ur.data?.user;
  if(!u)return NextResponse.json({message:'جلسة غير صالحة.'},{status:401});

  const cfgRes=await sb.rpc('get_kite_runtime_config');if(cfgRes.error)throw cfgRes.error;const cfg=cfgRes.data||{};
  if(cfg.allow_paid_external!==false||cfg.allow_paid_gpu===true||Number(cfg.daily_budget_usd||0)>0)return NextResponse.json({message:'سياسة zero-cost غير مضمونة؛ تم إيقاف الدورة.'},{status:409});

  const skills=(await sb.from('skill_state').select('domain,score,attempts,wins').order('score',{ascending:true}).order('attempts',{ascending:true})).data||[];
  let selected=null,target=null;
  for(const s of skills){
   const cr=await sb.from('benchmark_cases').select('id,suite,domain,difficulty,prompt,rubric,active').eq('active',true).eq('domain',s.domain).order('difficulty',{ascending:false}).limit(50);
   if(cr.error)throw cr.error;
   const eligible=(cr.data||[]).filter(c=>c.rubric?.held_out===true&&c.rubric?.teacher_generated===false&&c.rubric?.answer_type==='integer'&&Number.isFinite(Number(c.rubric?.exact_value)));
   if(!eligible.length)continue;
   const ids=eligible.map(c=>c.id),prior=await sb.from('benchmark_results').select('benchmark_case_id').in('benchmark_case_id',ids);if(prior.error)throw prior.error;
   const seen=new Set((prior.data||[]).map(r=>r.benchmark_case_id));selected=eligible.find(c=>!seen.has(c.id))||null;if(selected){target=s;break}
  }
  if(!selected)return NextResponse.json({message:'لا يوجد Benchmark يدوي held-out غير مُختبر وله oracle حتمي.',blocker:'no_unseen_objective_case'},{status:409});

  const prompt=String(selected.prompt||'').trim();if(!prompt)return NextResponse.json({message:'Benchmark غير صالح.'},{status:422});
  const origin=new URL(req.url).origin,sessionId=randomUUID(),conversationId=randomUUID(),started=Date.now();
  // /api/chat owns the free-provider rotation: OpenRouter -> Groq -> Gemini -> Mistral -> other explicitly-free/local fallbacks.
  const r=await fetch(origin+'/api/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({input:prompt+'\n\nاختم إجابتك بسطر مستقل بالشكل FINAL: <number>.',history:[],webSearch:false,sessionId,conversationId}),cache:'no-store',signal:AbortSignal.timeout(90000)});
  const d=await r.json().catch(()=>({}));
  if(!r.ok||!d?.text)return NextResponse.json({message:d?.message||'تعذر تشغيل KITE AI عبر جميع مزودي inference المجانيين المتاحين.',blocker:'free_inference_failed'},{status:r.status||503});

  const got=parseFinalInteger(d.text),expected=Number(selected.rubric.exact_value),score=got===expected?100:0,latency=Date.now()-started;
  const ins=await sb.from('benchmark_results').insert({owner_id:u.id,benchmark_case_id:selected.id,model_label:'KITE AI public runtime',answer:d.text,score,judge:'exact_integer_oracle',metadata:{held_out:true,teacher_generated:false,first_exposure:true,objective_verification:true,verification_method:'exact_integer_oracle',expected,observed:got,run_id:d.run_id||null,public_chat_log_id:d.chat_log_id||null,latency_ms:latency,cost_usd:0,student_provider:d.provider||null,student_model:d.model||null}}).select('id').single();if(ins.error)throw ins.error;

  const old=Number(target?.score)||0,attempts=(Number(target?.attempts)||0)+1,wins=(Number(target?.wins)||0)+(score>=85?1:0),next=Number((Number(target?.attempts)>0?old*0.7+score*0.3:score).toFixed(2));
  const su=await sb.from('skill_state').upsert({owner_id:u.id,domain:selected.domain,score:next,attempts,wins,updated_at:new Date().toISOString()},{onConflict:'owner_id,domain'});if(su.error)throw su.error;

  return NextResponse.json({ok:true,goal:'objective held-out evaluation',domain:selected.domain,task:prompt,answer:d.text,score,verified:true,verification_method:'exact_integer_oracle',new_skill_score:next,skill_updated:true,cost_usd:0,provider:d.provider||null,model:d.model||null,benchmark:{id:selected.id,suite:selected.suite,difficulty:selected.difficulty,seen_before:false},benchmark_result_id:ins.data?.id||null,latency_ms:latency});
 }catch(e){return NextResponse.json({message:e?.message||'فشلت دورة KITE AI.'},{status:500})}
}
