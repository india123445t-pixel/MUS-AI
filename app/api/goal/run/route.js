import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const OBJECTIVE_PROBE={
  domain:'math',
  prompt:'باستخدام الأرقام 1 و2 و3 و4 و5 و6 و7 مرة واحدة بالضبط، كم عدد الأعداد المكوّنة من 7 خانات التي تقبل القسمة على 11؟ أعط تبريرًا مختصرًا، واختم بسطر مستقل بالشكل FINAL: <number>.',
  reference:'576',
  rubric:{answer_type:'integer',exact_value:576,verification:'divisibility_rule_plus_exhaustive_enumeration',held_out:true,teacher_generated:false},
  suite:'MUS Objective Probe v0.1',
  id:'math-div11-permutation-001'
};

function client(token){if(!SUPABASE_URL||!SUPABASE_KEY)throw new Error('Supabase environment is not configured.');return createClient(SUPABASE_URL,SUPABASE_KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}})}
function normalizeEndpoint(raw){if(!raw)return null;const url=raw.replace(/\/$/,'');if(url.endsWith('/chat/completions'))return url;if(url.endsWith('/v1'))return `${url}/chat/completions`;return url}
function parseVerifier(raw=''){const match=String(raw).match(/\{[\s\S]*\}/);if(match){try{const j=JSON.parse(match[0]);return{score:Math.max(0,Math.min(100,Number(j.score)||0)),critique:String(j.critique||''),preferred:String(j.preferred_answer||'')}}catch{}}return{score:0,critique:'تعذر تفسير نتيجة المحقق.',preferred:''}}
function parseFinalInteger(text=''){const m=String(text).match(/(?:^|\n)\s*FINAL\s*[:=]\s*(-?\d+)\s*(?:$|\n)/i);return m?Number(m[1]):null}
function deterministicVerdict(rubric={},reference='',text=''){
  if(rubric?.answer_type==='integer'&&Number.isFinite(Number(rubric?.exact_value))){
    const got=parseFinalInteger(text),expected=Number(rubric.exact_value),pass=got===expected;
    return{objective:true,score:pass?100:0,critique:pass?'اجتاز التحقق الحتمي للقيمة النهائية.':`القيمة النهائية المتوقعة ${expected} بينما كانت ${got===null?'غير قابلة للاستخراج':got}.`,preferred:String(reference||expected),method:'exact_integer_oracle'};
  }
  return null;
}

async function localCall(messages,settings,temp=0.35){
  const endpoint=normalizeEndpoint(process.env.MUS_MODEL_URL||process.env.LOCAL_MODEL_URL);if(!endpoint)return null;
  try{const key=process.env.MUS_MODEL_KEY||process.env.LOCAL_MODEL_KEY;const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json',...(key?{Authorization:`Bearer ${key}`}:{})},body:JSON.stringify({model:settings?.self_hosted_model||process.env.MUS_MODEL_NAME||process.env.LOCAL_MODEL_NAME||'mus-ai',messages,temperature:temp,stream:false}),signal:AbortSignal.timeout(65000)});if(!r.ok)return null;const d=await r.json();const text=d?.choices?.[0]?.message?.content||d?.message?.content||d?.response||null;return text?{text,provider:'mus-engine',model:d?.model||settings?.self_hosted_model||'mus-ai'}:null}catch{return null}}
async function openRouterCall(messages,settings,temp=0.35,modelOverride=null){
  const key=process.env.OPENROUTER_API_KEY;if(!key)return null;
  let model=modelOverride||settings?.openrouter_model||process.env.OPENROUTER_MODEL||'openrouter/free';
  if(!settings?.allow_paid_external&&!String(model).includes(':free')&&model!=='openrouter/free')model='openrouter/free';
  try{const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{method:'POST',headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json','X-Title':'MUS AI Goal Engine'},body:JSON.stringify({model,messages,temperature:temp}),signal:AbortSignal.timeout(70000)});const d=await r.json();if(!r.ok)return null;const text=d?.choices?.[0]?.message?.content||null;return text?{text,provider:'openrouter',model:d?.model||model}:null}catch{return null}}
async function runtimeCall(messages,settings,temp=0.35){const mode=settings?.runtime_mode||'openrouter_primary';if(mode==='openrouter_primary'||mode==='openrouter_only')return await openRouterCall(messages,settings,temp)||(mode==='openrouter_only'?null:await localCall(messages,settings,temp));return await localCall(messages,settings,temp)||(mode==='self_hosted_only'?null:await openRouterCall(messages,settings,temp))}
async function independentJudge(messages,settings){return await openRouterCall(messages,settings,0.1,process.env.MUS_JUDGE_MODEL||'openrouter/free')||await runtimeCall(messages,settings,0.1)}

export async function POST(req){
  try{
    const auth=req.headers.get('authorization')||'',token=auth.startsWith('Bearer ')?auth.slice(7):'';if(!token)return NextResponse.json({message:'يلزم تسجيل الدخول.'},{status:401});
    const body=await req.json().catch(()=>({}));
    const sb=client(token),userRes=await sb.auth.getUser(),u=userRes.data?.user;if(!u)return NextResponse.json({message:'جلسة غير صالحة.'},{status:401});
    const [goalRes,skillsRes,cfgRes]=await Promise.all([
      sb.from('goals').select('*').eq('status','active').order('priority',{ascending:false}).limit(1).maybeSingle(),
      sb.from('skill_state').select('domain,score,attempts,wins').order('score',{ascending:true}).order('attempts',{ascending:true}).limit(8),
      sb.rpc('get_mus_runtime_config')
    ]);
    const goal=goalRes.data;if(!goal)return NextResponse.json({message:'لا يوجد هدف نشط لـ MUS AI.'},{status:404});
    const settings=cfgRes.data||{},skills=skillsRes.data||[];
    let target=skills[0]||{domain:'reasoning',score:0,attempts:0,wins:0},domain=target.domain;

    let benchmark=null,challenge='',reference='',rubric={},builtInProbe=false;
    const probeSeen=await sb.from('goal_runs').select('id',{count:'exact',head:true}).eq('task',OBJECTIVE_PROBE.prompt);
    if(body?.objectiveProbe===true||(probeSeen.count||0)===0){
      builtInProbe=true;domain=OBJECTIVE_PROBE.domain;target=skills.find(x=>x.domain===domain)||{domain,score:0,attempts:0,wins:0};challenge=OBJECTIVE_PROBE.prompt;reference=OBJECTIVE_PROBE.reference;rubric=OBJECTIVE_PROBE.rubric;
    }else{
      const casesRes=await sb.from('benchmark_cases').select('*').eq('active',true).eq('domain',domain).order('difficulty',{ascending:false}).limit(20);
      const cases=casesRes.data||[];
      if(cases.length){
        const ids=cases.map(x=>x.id),priorRes=await sb.from('benchmark_results').select('benchmark_case_id').in('benchmark_case_id',ids),counts={};
        for(const r of priorRes.data||[])counts[r.benchmark_case_id]=(counts[r.benchmark_case_id]||0)+1;
        benchmark=[...cases].sort((a,b)=>(counts[a.id]||0)-(counts[b.id]||0)||Number(b.difficulty||0)-Number(a.difficulty||0))[0];challenge=benchmark.prompt;reference=benchmark.reference_answer||'';rubric=benchmark.rubric||{};
      }else{
        const seed=await independentJudge([{role:'system',content:'أنشئ سؤال تطوير واحدًا صعبًا لكن قابلًا للتحقق موضوعيًا. لا تعط الحل. هذا سؤال تطوير وليس اختبار ترقية مخفي.'},{role:'user',content:`المجال: ${domain}. الهدف: ${goal.objective}`}],settings);
        if(!seed)return NextResponse.json({message:'لا يوجد محرك مجاني متاح لإنشاء تحدي تطوير.'},{status:503});challenge=seed.text.trim().slice(0,12000);
      }
    }

    const exactOracle=rubric?.answer_type==='integer'&&Number.isFinite(Number(rubric?.exact_value));
    const studentSystem=exactOracle?'أنت MUS AI. حل المهمة بأعلى دقة ممكنة. لا تختلق حقائق أو تنفيذًا لم يحدث. أعط تبريرًا موجزًا قابلًا للتحقق، واختم بسطر مستقل FINAL: <number>. لا تعرض سلسلة تفكير خاصة.':'أنت MUS AI. حل المهمة بأعلى دقة ممكنة. لا تختلق حقائق أو تنفيذًا لم يحدث. أعط الجواب النهائي مع تبرير موجز قابل للتحقق، ولا تعرض سلسلة تفكير خاصة.';
    const student=await runtimeCall([{role:'system',content:studentSystem},{role:'user',content:challenge}],settings,0.3);
    if(!student)return NextResponse.json({message:'تعذر تشغيل MUS AI، ولم يتم استخدام مورد مدفوع.'},{status:503});

    let verdict=deterministicVerdict(rubric,reference,student.text),judge=null;
    if(!verdict){
      const judgePrompt=benchmark?`المجال: ${domain}\nالمهمة:\n${challenge}\n\nالجواب المرجعي:\n${reference}\n\nRubric:\n${JSON.stringify(rubric)}\n\nإجابة MUS AI:\n${student.text}`:`المجال: ${domain}\nالمهمة التطويرية:\n${challenge}\n\nإجابة MUS AI:\n${student.text}`;
      judge=await independentJudge([{role:'system',content:'أنت محقق مستقل وصارم. قيّم الصحة لا الأسلوب. أعد JSON فقط: {"score":0-100,"critique":"ملاحظة قصيرة قابلة للإصلاح","preferred_answer":"أفضل جواب صحيح مختصر"}. هذا الحكم تشخيصي ولا يثبت تحسن المهارة وحده.'},{role:'user',content:judgePrompt}],settings);
      if(!judge)return NextResponse.json({message:'تعذر تشغيل المحقق المجاني. لم يتم اعتماد أي تعلم.'},{status:503});const j=parseVerifier(judge.text);verdict={...j,objective:false,method:'model_judgment'};
    }

    let seenBefore=false;
    if(benchmark){const c=await sb.from('benchmark_results').select('id',{count:'exact',head:true}).eq('benchmark_case_id',benchmark.id);seenBefore=(c.count||0)>0}
    const runInsert=await sb.from('goal_runs').insert({owner_id:u.id,goal_id:goal.id,domain,task:challenge,answer:student.text,verifier_notes:`${verdict.method}: ${verdict.critique}`,score:verdict.objective?verdict.score:null,cost_usd:0,provider:student.provider,model:student.model,outcome:verdict.objective?(verdict.score>=85?'objective_pass':'objective_fail'):'diagnostic_unverified'}).select('id').single();

    let newSkillScore=Number(target.score)||0;
    if(verdict.objective){
      const old=Number(target.score)||0,weight=Number(target.attempts)>0?(seenBefore?0.10:0.30):1;newSkillScore=Number((Number(target.attempts)>0?old*(1-weight)+verdict.score*weight:verdict.score).toFixed(2));
      const wins=(Number(target.wins)||0)+(verdict.score>=85?1:0),attempts=(Number(target.attempts)||0)+1;
      await sb.from('skill_state').upsert({owner_id:u.id,domain,score:newSkillScore,attempts,wins,updated_at:new Date().toISOString()},{onConflict:'owner_id,domain'});
    }

    if(benchmark){
      await sb.from('benchmark_results').insert({owner_id:u.id,benchmark_case_id:benchmark.id,model_label:'MUS AI runtime',answer:student.text,score:verdict.objective?verdict.score:null,judge:verdict.objective?verdict.method:(judge?.model||judge?.provider||'model_judgment'),metadata:{goal_run_id:runInsert.data?.id||null,suite:benchmark.suite,objective_verification:verdict.objective,verification_method:verdict.method,seen_before:seenBefore,student_provider:student.provider,student_model:student.model}});
    }
    if(verdict.objective&&verdict.score<85&&reference){
      await sb.from('training_examples').insert({owner_id:u.id,user_input:challenge,assistant_bad_answer:student.text,preferred_answer:reference,category:domain,tags:['objective-failure','reference-grounded'],quality_status:'candidate',context_snapshot:{benchmark_case_id:benchmark?.id||null,probe_id:builtInProbe?OBJECTIVE_PROBE.id:null,score:verdict.score,verification_method:verdict.method,source:'objective-reference',goal_run_id:runInsert.data?.id||null}});
    }

    return NextResponse.json({ok:true,goal:goal.name,domain,task:challenge,answer:student.text,score:verdict.objective?verdict.score:null,diagnostic_score:verdict.objective?null:verdict.score,verified:verdict.objective,verification_method:verdict.method,critique:verdict.critique,preferred_answer:reference||verdict.preferred,new_skill_score:newSkillScore,cost_usd:0,provider:student.provider,model:student.model,benchmark:benchmark?{id:benchmark.id,suite:benchmark.suite,difficulty:benchmark.difficulty,seen_before:seenBefore}:builtInProbe?{id:OBJECTIVE_PROBE.id,suite:OBJECTIVE_PROBE.suite,difficulty:4,seen_before:(probeSeen.count||0)>0}:null});
  }catch(e){return NextResponse.json({message:e?.message||'فشلت دورة التعلم.'},{status:500})}
}
