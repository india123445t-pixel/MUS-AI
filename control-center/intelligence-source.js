'use client';

import {useEffect,useMemo,useState} from 'react';
import {createClient} from '@supabase/supabase-js';
import {advisoryConfidence,formalLearningEligible,isDeepRoute,isUnresolvedTrace,isVerifiedTrace,traceDomain,verificationLabel} from '../../../lib/kite/control-center-compat.js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL,KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const names={reasoning:'الاستدلال',math:'الرياضيات',science:'العلوم',coding:'البرمجة',language:'اللغة',research:'البحث',planning:'التخطيط',knowledge:'المعرفة',general:'عام',software:'البرمجة',data:'البيانات',communication:'التواصل',operations:'العمليات'};
function Metric({label,value,sub}){return <div className="metric-card"><span>{label}</span><strong>{value}</strong>{sub&&<small>{sub}</small>}</div>}
function pct(n){return `${Math.round((Number(n)||0)*100)}%`}

export default function IntelligenceLab(){
  const sb=useMemo(()=>URL&&KEY?createClient(URL,KEY):null,[]);
  const [ready,setReady]=useState(false),[session,setSession]=useState(null),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[authMsg,setAuthMsg]=useState('');
  const [settings,setSettings]=useState(null),[logs,setLogs]=useState([]),[bench,setBench]=useState([]),[skills,setSkills]=useState([]),[examples,setExamples]=useState([]),[busy,setBusy]=useState(false),[msg,setMsg]=useState('');

  useEffect(()=>{if(!sb){setReady(true);return}sb.auth.getSession().then(({data})=>{setSession(data.session||null);setReady(true)});const{data}=sb.auth.onAuthStateChange((_e,s)=>setSession(s));return()=>data.subscription.unsubscribe()},[sb]);
  useEffect(()=>{if(session)load()},[session]);
  async function login(e){e.preventDefault();setAuthMsg('');const r=await sb.auth.signInWithPassword({email,password});if(r.error)setAuthMsg('بيانات الدخول غير صحيحة.')}
  async function load(){setBusy(true);setMsg('');try{const u=(await sb.auth.getUser()).data.user;const [cfg,lg,br,sk,ex]=await Promise.all([
    sb.from('control_settings').select('*').eq('owner_id',u.id).single(),
    sb.from('public_chat_logs').select('id,created_at,task_contract,route_decision,verification,latency_ms,model_calls,difficulty,learning_eligible,model,provider').order('created_at',{ascending:false}).limit(200),
    sb.from('benchmark_results').select('id,score,created_at,benchmark_case_id,model_label,judge,metadata').order('created_at',{ascending:false}).limit(200),
    sb.from('skill_state').select('*').order('score',{ascending:true}),
    sb.from('training_examples').select('id,quality_status,tags,created_at').order('created_at',{ascending:false}).limit(300)
  ]);setSettings(cfg.data||null);setLogs(lg.data||[]);setBench(br.data||[]);setSkills(sk.data||[]);setExamples(ex.data||[])}catch(e){setMsg(e.message||'تعذر تحميل المختبر.')}finally{setBusy(false)}}
  async function save(){if(!settings)return;setBusy(true);setMsg('');const patch={intelligence_router_enabled:!!settings.intelligence_router_enabled,verification_enabled:!!settings.verification_enabled,deep_reasoning_enabled:!!settings.deep_reasoning_enabled,max_model_calls_per_request:Number(settings.max_model_calls_per_request||3)};const {error}=await sb.from('control_settings').update(patch).eq('owner_id',settings.owner_id);setBusy(false);setMsg(error?error.message:'تم حفظ إعدادات Intelligence Kernel.');if(!error)load()}
  async function runBenchmark(){if(!session)return;setBusy(true);setMsg('');try{const r=await fetch('/api/benchmark/run',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:'{}'}),d=await r.json();if(!r.ok)throw Error(d.message||'فشل الاختبار');setMsg(`Benchmark ${names[d.domain]||d.domain}: ${d.score}/100${d.suite?' — '+d.suite:''}`);await load()}catch(e){setMsg(e.message)}finally{setBusy(false)}}

  if(!URL||!KEY)return <div className="center-screen"><div className="error-box">إعداد Supabase غير مكتمل.</div></div>;
  if(!ready)return <div className="center-screen"><div className="brand-loader"><img src="/icon.svg" alt=""/><b>KITE AI</b></div></div>;
  if(!session)return <div className="admin-login-shell"><form className="admin-login-card" onSubmit={login}><img src="/icon.svg" alt="KITE AI"/><span className="eyebrow">INTELLIGENCE LAB</span><h1>KITE AI</h1><p>قياس وتحسين الذكاء الموثق.</p><label>البريد الإلكتروني<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>كلمة المرور<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label><button className="primary-btn" type="submit">دخول</button>{authMsg&&<div className="auth-msg">{authMsg}</div>}</form></div>;

  const verified=logs.filter(isVerifiedTrace).length,uncertain=logs.filter(isUnresolvedTrace).length;
  const avgLatency=logs.length?Math.round(logs.reduce((a,x)=>a+Number(x.latency_ms||0),0)/logs.length):0;
  const avgCalls=logs.length?(logs.reduce((a,x)=>a+Number(x.model_calls||0),0)/logs.length).toFixed(2):'0';
  const deep=logs.filter(isDeepRoute).length;
  const benchAvg=bench.length?(bench.reduce((a,x)=>a+Number(x.score||0),0)/bench.length).toFixed(1):'—';
  const learning=logs.filter(formalLearningEligible).length,candidates=examples.filter(x=>x.quality_status==='candidate').length;

  return <main className="admin-main" dir="rtl" style={{maxWidth:1280}}><header className="admin-header"><div><span className="eyebrow">KITE AI · INTELLIGENCE LAB</span><h1>مختبر الذكاء والقياس</h1></div><div className="header-actions"><a className="ghost-fit" href="/">مركز التحكم</a><button className="refresh-btn" onClick={load} disabled={busy}>{busy?'…':'تحديث'}</button></div></header>{msg&&<div className="admin-notice">{msg}</div>}

  <section className="metric-grid"><Metric label="Benchmark" value={benchAvg==='—'?'—':`${benchAvg}/100`} sub={`${bench.length} نتائج`}/><Metric label="Verified" value={logs.length?`${Math.round(verified/logs.length*100)}%`:'—'} sub={`${verified} من ${logs.length}`}/><Metric label="متوسط الاستدعاءات" value={avgCalls} sub={`${deep} طلبات Deep`}/><Metric label="زمن متوسط" value={avgLatency?`${avgLatency}ms`:'—'} sub={`${uncertain} غير محسومة`}/></section>

  <section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">INTELLIGENCE KERNEL</span><h3>سياسة التفكير</h3><p>السهل يبقى رخيصًا، والصعب يأخذ تحققًا وحسابًا إضافيًا.</p></div></div>{settings&&<><div className="control-row"><label className="switch-row"><input type="checkbox" checked={!!settings.intelligence_router_enabled} onChange={e=>setSettings({...settings,intelligence_router_enabled:e.target.checked})}/><span><b>Intelligence Router</b><small>تصنيف المهمة وتخصيص الحساب</small></span></label><label className="switch-row"><input type="checkbox" checked={!!settings.verification_enabled} onChange={e=>setSettings({...settings,verification_enabled:e.target.checked})}/><span><b>Verifier</b><small>مراجعة استشارية؛ لا تمنح VERIFIED بنفسها</small></span></label><label className="switch-row"><input type="checkbox" checked={!!settings.deep_reasoning_enabled} onChange={e=>setSettings({...settings,deep_reasoning_enabled:e.target.checked})}/><span><b>Deep Reasoning</b><small>مسار reasoning عميق عند الحاجة</small></span></label></div><div className="form-grid"><label>أقصى استدعاءات للنموذج<input type="number" min="1" max="4" value={settings.max_model_calls_per_request||3} onChange={e=>setSettings({...settings,max_model_calls_per_request:Number(e.target.value)})}/></label><div><span>بوابة التعلم الرسمية</span><b>VerificationState = VERIFIED</b><small>تم إلغاء التحكم القديم المبني على confidence؛ القيمة القديمة لا تتحكم في BOS.</small></div></div><button className="primary-btn fit" onClick={save} disabled={busy}>حفظ السياسة</button></>}</div>
  <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">EVALUATION</span><h3>اختبار KITE AI</h3><p>يشغّل أضعف مجال على Benchmark مرجعي قبل أي تعلم.</p></div></div><div className="status-list"><div><span>النموذج الحالي</span><b>{settings?.openrouter_model||'—'}</b></div><div><span>وضع التشغيل</span><b>{settings?.runtime_mode||'—'}</b></div><div><span>بحث مدفوع</span><b>{settings?.allow_paid_external&&settings?.public_web_search_enabled?'مسموح':'مغلق'}</b></div><div><span>مرشحو التعلم الموثقون</span><b>{learning}</b></div><div><span>Training candidates</span><b>{candidates}</b></div></div><button className="primary-btn fit" onClick={runBenchmark} disabled={busy} style={{marginTop:14}}>تشغيل Benchmark واحد</button></div></section>

  <section className="admin-panel wide" style={{marginTop:12}}><div className="panel-head"><div><span className="eyebrow">SKILL MAP</span><h3>القدرات المقاسة</h3></div></div><div className="skill-cards">{skills.map(s=><div className="skill-card" key={s.domain}><div className="skill-card-head"><div><span>{names[s.domain]||s.domain}</span><small>{s.attempts||0} اختبارات · {s.wins||0} نجاحات</small></div><strong>{Number(s.score||0).toFixed(0)}</strong></div><div className="skill-meter"><i style={{width:`${Math.max(2,Number(s.score)||0)}%`}}/></div></div>)}</div></section>

  <section className="admin-panel wide" style={{marginTop:12}}><div className="panel-head"><div><span className="eyebrow">REQUEST TRACES</span><h3>آخر قرارات الذكاء</h3><p>يعرض هذا السجل معنى BOS الحالي دون إعادة تفسير verdict/confidence القديم كحقيقة رسمية.</p></div></div><div className="table-list">{logs.length?logs.slice(0,40).map(x=>{const confidence=advisoryConfidence(x.verification);const domain=traceDomain(x);return <div className="table-row" key={x.id}><div><b>{names[domain]||domain||'عام'} · {x.difficulty||'—'}</b><span>{x.route_decision?.mode||'NORMAL'} · {x.route_decision?.reasoning||'standard'} · {x.route_decision?.web_search?'web':'no-web'} · {formalLearningEligible(x)?'learning candidate':'no learning'}</span></div><span>{verificationLabel(x.verification)} {confidence!=null?`advisory ${pct(confidence)}`:''}</span><strong>{x.model_calls||1} calls</strong><span>{x.latency_ms?`${x.latency_ms}ms`:'—'}</span></div>}):<div className="empty-panel">لا توجد traces جديدة بعد. استخدم التطبيق وسيبدأ القياس تلقائيًا.</div>}</div></section>
  </main>
}
