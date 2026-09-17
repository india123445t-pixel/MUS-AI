import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function parseFinalInteger(text=''){
  const m=String(text).match(/(?:^|\n)\s*FINAL\s*[:=]\s*(-?\d+)\s*(?:$|\n)/i);
  return m?Number(m[1]):null;
}

function client(token){
  if(!URL||!KEY)throw new Error('Supabase environment is not configured.');
  return createClient(URL,KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}});
}

function providerFlags(){
  return {
    openrouter:!!process.env.OPENROUTER_API_KEY,
    groq:!!process.env.GROQ_API_KEY,
    gemini:!!(process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY),
    mistral:!!process.env.MISTRAL_API_KEY,
    cerebras:!!process.env.CEREBRAS_API_KEY,
    huggingface:!!process.env.HF_TOKEN&&process.env.HF_FREE_FALLBACK_ENABLED==='true',
    self_hosted:!!(process.env.AQLEVON_MODEL_URL||process.env.LOCAL_MODEL_URL)
  };
}

export async function POST(req){
  try{
    const auth=req.headers.get('authorization')||'';
    const token=auth.startsWith('Bearer ')?auth.slice(7):'';
    if(!token)return NextResponse.json({message:'يلزم تسجيل الدخول.'},{status:401});

    const sb=client(token);
    const userResult=await sb.auth.getUser();
    const user=userResult.data?.user;
    if(userResult.error||!user)return NextResponse.json({message:'جلسة غير صالحة.'},{status:401});

    const runtimeResult=await sb.rpc('get_aqlevon_runtime_config');
    if(runtimeResult.error)throw runtimeResult.error;
    const settings=runtimeResult.data||{};
    if(settings.allow_paid_external!==false||settings.allow_paid_gpu===true||Number(settings.daily_budget_usd||0)>0){
      return NextResponse.json({message:'تم إيقاف Benchmark لأن سياسة zero-cost غير مضمونة.'},{status:409});
    }

    const providers=providerFlags();
    if(!Object.values(providers).some(Boolean)){
      return NextResponse.json({message:'لا يوجد inference provider مجاني/محلي مُهيأ حاليًا.',blocker:'no_zero_cost_provider'},{status:503});
    }

    const skillResult=await sb.from('skill_state').select('domain,score,attempts,wins').order('score',{ascending:true}).order('attempts',{ascending:true});
    if(skillResult.error)throw skillResult.error;

    let selected=null,target=null;
    for(const skill of skillResult.data||[]){
      const caseResult=await sb.from('benchmark_cases').select('id,suite,domain,difficulty,prompt,rubric,active').eq('active',true).eq('domain',skill.domain).order('difficulty',{ascending:false}).limit(50);
      if(caseResult.error)throw caseResult.error;
      const eligible=(caseResult.data||[]).filter(c=>
        c.rubric?.held_out===true&&
        c.rubric?.teacher_generated===false&&
        c.rubric?.answer_type==='integer'&&
        Number.isFinite(Number(c.rubric?.exact_value))
      );
      if(!eligible.length)continue;
      const ids=eligible.map(c=>c.id);
      const priorResult=await sb.from('benchmark_results').select('benchmark_case_id').in('benchmark_case_id',ids);
      if(priorResult.error)throw priorResult.error;
      const seen=new Set((priorResult.data||[]).map(r=>r.benchmark_case_id));
      selected=eligible.find(c=>!seen.has(c.id))||null;
      if(selected){target=skill;break;}
    }

    if(!selected)return NextResponse.json({message:'لا يوجد Benchmark يدوي held-out غير مُختبر وله oracle حتمي.',blocker:'no_unseen_objective_case'},{status:409});

    const prompt=String(selected.prompt||'').trim();
    if(!prompt)return NextResponse.json({message:'Benchmark غير صالح.'},{status:422});

    const sessionId=crypto.randomUUID();
    const conversationId=crypto.randomUUID();
    const origin=new URL(req.url).origin;
    const started=Date.now();
    const chat=await fetch(`${origin}/api/chat`,{
      method:'POST',
      headers:{'content-type':'application/json'},
      body:JSON.stringify({
        input:`${prompt}\n\nاختم إجابتك بسطر مستقل بالشكل FINAL: <number>.`,
        history:[],
        webSearch:false,
        sessionId,
        conversationId
      }),
      cache:'no-store',
      signal:AbortSignal.timeout(90000)
    });
    const payload=await chat.json().catch(()=>({}));
    if(!chat.ok||!payload?.text){
      return NextResponse.json({message:payload?.message||'تعذر تشغيل AQLEVON AI على الاختبار.',blocker:'inference_failed'},{status:chat.status||502});
    }

    const observed=parseFinalInteger(payload.text);
    const expected=Number(selected.rubric.exact_value);
    const score=observed===expected?100:0;
    const latencyMs=Date.now()-started;

    const insert=await sb.from('benchmark_results').insert({
      owner_id:user.id,
      benchmark_case_id:selected.id,
      model_label:'AQLEVON AI public runtime',
      answer:payload.text,
      score,
      judge:'exact_integer_oracle',
      metadata:{
        held_out:true,
        teacher_generated:false,
        first_exposure:true,
        objective_verification:true,
        verification_method:'exact_integer_oracle',
        expected,
        observed,
        run_id:payload.run_id||null,
        public_chat_log_id:payload.chat_log_id||null,
        latency_ms:latencyMs,
        cost_usd:0
      }
    }).select('id').single();
    if(insert.error)throw insert.error;

    const oldScore=Number(target?.score)||0;
    const attempts=(Number(target?.attempts)||0)+1;
    const wins=(Number(target?.wins)||0)+(score>=85?1:0);
    const nextScore=Number((Number(target?.attempts)>0?oldScore*0.7+score*0.3:score).toFixed(2));
    const skillUpdate=await sb.from('skill_state').upsert({
      owner_id:user.id,
      domain:selected.domain,
      score:nextScore,
      attempts,
      wins,
      updated_at:new Date().toISOString()
    },{onConflict:'owner_id,domain'});
    if(skillUpdate.error)throw skillUpdate.error;

    return NextResponse.json({
      ok:true,
      benchmark_result_id:insert.data?.id||null,
      benchmark_id:selected.id,
      suite:selected.suite,
      domain:selected.domain,
      difficulty:selected.difficulty,
      score,
      expected,
      observed,
      first_exposure:true,
      new_skill_score:nextScore,
      run_id:payload.run_id||null,
      chat_log_id:payload.chat_log_id||null,
      latency_ms:latencyMs,
      cost_usd:0,
      verified:true,
      verification_method:'exact_integer_oracle'
    },{headers:{'Cache-Control':'no-store'}});
  }catch(e){
    return NextResponse.json({message:e?.message||'فشل تشغيل Benchmark.'},{status:500});
  }
}
