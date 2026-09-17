'use client';

import {useEffect,useMemo,useState} from 'react';
import {createClient} from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

const domainNames={reasoning:'الاستدلال',math:'الرياضيات',science:'العلوم',coding:'البرمجة',language:'اللغة',research:'البحث',planning:'التخطيط',knowledge:'المعرفة',general:'عام',software:'البرمجة',data:'البيانات',communication:'التواصل',operations:'العمليات'};
const safeModes=['openrouter_primary','openrouter_only','self_hosted_primary','self_hosted_only'];

function Metric({label,value,sub}){
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong>{sub&&<small>{sub}</small>}</div>;
}
function resultOf(v){return String(v?.result||'').toUpperCase()}
function isVerified(log){return resultOf(log?.verification)==='VERIFIED'}
function learningEligible(log){return isVerified(log)&&log?.learning_eligible===true}
function traceDomain(log){return log?.task_contract?.primary_domain||log?.task_contract?.domain||'general'}
function freeModel(v){const s=String(v||'openrouter/free').trim();return s==='openrouter/free'||s.endsWith(':free')?s:'openrouter/free'}

export default function AdminPage(){
  const sb=useMemo(()=>URL&&KEY?createClient(URL,KEY):null,[]);
  const [ready,setReady]=useState(false),[session,setSession]=useState(null),[authorized,setAuthorized]=useState(false);
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[authMsg,setAuthMsg]=useState('');
  const [status,setStatus]=useState(null),[settings,setSettings]=useState(null),[logs,setLogs]=useState([]),[examples,setExamples]=useState([]),[bench,setBench]=useState([]),[skills,setSkills]=useState([]);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');

  useEffect(()=>{
    if(!sb){setReady(true);return}
    sb.auth.getSession().then(({data})=>{setSession(data.session||null);setReady(true)});
    const {data}=sb.auth.onAuthStateChange((_event,s)=>setSession(s));
    return()=>data.subscription.unsubscribe();
  },[sb]);

  useEffect(()=>{if(session)loadAll();else setAuthorized(false)},[session]);

  async function login(e){
    e.preventDefault();setAuthMsg('');
    const r=await sb.auth.signInWithPassword({email,password});
    if(r.error)setAuthMsg('بيانات الدخول غير صحيحة.');
  }

  async function loadAll(){
    setBusy(true);setNotice('');
    try{
      const user=(await sb.auth.getUser()).data.user;
      if(!user)throw new Error('جلسة غير صالحة.');
      const owner=await sb.from('system_owner').select('owner_id').eq('owner_id',user.id).maybeSingle();
      if(owner.error||!owner.data){setAuthorized(false);await sb.auth.signOut();throw new Error('هذا الحساب غير مخول لإدارة AQLEVON.');}
      setAuthorized(true);

      const [st,cfg,lg,ex,br,sk]=await Promise.all([
        fetch('/api/status',{cache:'no-store'}).then(r=>r.json()),
        sb.from('control_settings').select('*').eq('owner_id',user.id).single(),
        sb.from('public_chat_logs').select('id,created_at,task_contract,route_decision,verification,latency_ms,model_calls,difficulty,learning_eligible,model,provider').order('created_at',{ascending:false}).limit(120),
        sb.from('training_examples').select('id,user_input,preferred_answer,quality_status,tags,context_snapshot,created_at').order('created_at',{ascending:false}).limit(150),
        sb.from('benchmark_results').select('id,score,created_at,model_label,judge').order('created_at',{ascending:false}).limit(100),
        sb.from('skill_state').select('domain,score,attempts,wins').order('score',{ascending:true})
      ]);
      setStatus(st||null);setSettings(cfg.data||null);setLogs(lg.data||[]);setExamples(ex.data||[]);setBench(br.data||[]);setSkills(sk.data||[]);
    }catch(e){setNotice(e?.message||'تعذر تحميل لوحة التحكم.')}finally{setBusy(false)}
  }

  async function saveRuntime(){
    if(!settings)return;
    setBusy(true);setNotice('');
    try{
      const mode=safeModes.includes(settings.runtime_mode)?settings.runtime_mode:'openrouter_primary';
      const patch={
        runtime_mode:mode,
        openrouter_model:freeModel(settings.openrouter_model),
        temperature:Math.max(0,Math.min(2,Number(settings.temperature??0.6))),
        max_history:Math.max(4,Math.min(64,Number(settings.max_history||16))),
        public_chat_enabled:!!settings.public_chat_enabled,
        public_training_enabled:!!settings.public_training_enabled,
        save_training_candidates:!!settings.save_training_candidates,
        intelligence_router_enabled:!!settings.intelligence_router_enabled,
        verification_enabled:!!settings.verification_enabled,
        deep_reasoning_enabled:!!settings.deep_reasoning_enabled,
        max_model_calls_per_request:Math.max(1,Math.min(4,Number(settings.max_model_calls_per_request||3))),
        allow_paid_external:false,
        daily_budget_usd:0
      };
      const {error}=await sb.from('control_settings').update(patch).eq('owner_id',settings.owner_id);
      if(error)throw error;
      setNotice('تم حفظ إعدادات AQLEVON مع إبقاء الإنفاق المدفوع مقفلاً عند صفر.');
      await loadAll();
    }catch(e){setNotice(e?.message||'تعذر حفظ الإعدادات.')}finally{setBusy(false)}
  }

  async function runBenchmark(){
    if(!session)return;
    setBusy(true);setNotice('');
    try{
      const r=await fetch('/api/benchmark/run',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:'{}'});
      const d=await r.json();if(!r.ok)throw new Error(d.message||'فشل الاختبار.');
      setNotice(`Benchmark ${domainNames[d.domain]||d.domain}: ${d.score}/100`);
      await loadAll();
    }catch(e){setNotice(e?.message||'فشل Benchmark.')}finally{setBusy(false)}
  }

  async function promoteTrace(id){
    setBusy(true);setNotice('');
    try{
      const {data,error}=await sb.rpc('promote_verified_chat_to_training',{p_chat_log_id:id});
      if(error)throw error;
      setNotice(`تمت ترقية الـtrace إلى Training Candidate: ${data}`);
      await loadAll();
    }catch(e){setNotice(e?.message||'تعذر ترقية الـtrace.')}finally{setBusy(false)}
  }

  async function reviewExample(id,quality_status){
    setBusy(true);setNotice('');
    try{
      const {error}=await sb.from('training_examples').update({quality_status}).eq('id',id);
      if(error)throw error;
      setNotice(quality_status==='approved'?'تم اعتماد المثال.':'تم رفض المثال.');
      await loadAll();
    }catch(e){setNotice(e?.message||'تعذر تحديث المثال.')}finally{setBusy(false)}
  }

  if(!URL||!KEY)return <div className="center-screen"><div className="error-box">إعداد Supabase غير مكتمل.</div></div>;
  if(!ready)return <div className="center-screen"><div className="brand-loader"><img src="/icon.svg" alt=""/><b>AQLEVON AI</b></div></div>;
  if(!session)return <div className="admin-login-shell"><form className="admin-login-card" onSubmit={login}><img src="/icon.svg" alt="AQLEVON AI"/><span className="eyebrow">PRIVATE CONTROL CENTER</span><h1>AQLEVON AI</h1><p>لوحة الإدارة الخاصة بالمشروع.</p><label>البريد الإلكتروني<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>كلمة المرور<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label><button className="primary-btn" type="submit">دخول</button>{authMsg&&<div className="auth-msg">{authMsg}</div>}</form></div>;
  if(!authorized&&!busy)return <div className="center-screen"><div className="error-box">غير مصرح لهذا الحساب.</div></div>;

  const verified=logs.filter(isVerified).length;
  const eligible=logs.filter(learningEligible);
  const promotedIds=new Set(examples.map(x=>x.context_snapshot?.public_chat_log_id).filter(Boolean).map(String));
  const candidates=examples.filter(x=>x.quality_status==='candidate');
  const approved=examples.filter(x=>x.quality_status==='approved');
  const avgBench=bench.length?(bench.reduce((a,x)=>a+Number(x.score||0),0)/bench.length).toFixed(1):'—';
  const avgSkill=skills.length?(skills.reduce((a,x)=>a+Number(x.score||0),0)/skills.length).toFixed(0):'—';

  return <main className="admin-main" dir="rtl" style={{maxWidth:1380,margin:'0 auto'}}>
    <header className="admin-header"><div><span className="eyebrow">AQLEVON AI · CONTROL CENTER</span><h1>لوحة التحكم السيادية</h1></div><div className="header-actions"><a className="ghost-fit" href="/">فتح التطبيق</a><button className="refresh-btn" onClick={loadAll} disabled={busy}>{busy?'…':'تحديث'}</button><button className="ghost-fit" onClick={()=>sb.auth.signOut()}>خروج</button></div></header>
    {notice&&<div className="admin-notice">{notice}</div>}

    <section className="metric-grid">
      <Metric label="الحالة" value={status?.openrouter_configured||status?.self_hosted_configured?'متصل':'يحتاج إعداد'} sub={settings?.runtime_mode||'—'}/>
      <Metric label="Verified" value={logs.length?`${Math.round(verified/logs.length*100)}%`:'—'} sub={`${verified} من ${logs.length}`}/>
      <Metric label="Benchmark" value={avgBench==='—'?'—':`${avgBench}/100`} sub={`${bench.length} نتائج`}/>
      <Metric label="متوسط القدرات" value={avgSkill==='—'?'—':`${avgSkill}/100`} sub={`${skills.length} مجالات`}/>
      <Metric label="مرشحو التعلم" value={eligible.length} sub={`${candidates.length} candidates`}/>
      <Metric label="أمثلة معتمدة" value={approved.length} sub="جاهزة للداتا سيت"/>
    </section>

    <section className="panel-grid" style={{marginTop:12}}>
      <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">RUNTIME</span><h3>المحرك والسياسة</h3><p>الإنفاق المدفوع مقفول في هذه المرحلة.</p></div></div>{settings&&<div className="form-grid">
        <label>وضع التشغيل<select value={settings.runtime_mode||'openrouter_primary'} onChange={e=>setSettings({...settings,runtime_mode:e.target.value})}><option value="openrouter_primary">OpenRouter Free أولًا</option><option value="openrouter_only">OpenRouter Free فقط</option><option value="self_hosted_primary">AQLEVON Self-hosted أولًا</option><option value="self_hosted_only">AQLEVON Self-hosted فقط</option></select></label>
        <label>نموذج OpenRouter المجاني<input value={settings.openrouter_model||'openrouter/free'} onChange={e=>setSettings({...settings,openrouter_model:e.target.value})}/></label>
        <label>Temperature<input type="number" min="0" max="2" step="0.1" value={settings.temperature??0.6} onChange={e=>setSettings({...settings,temperature:Number(e.target.value)})}/></label>
        <label>سياق المحادثة<input type="number" min="4" max="64" value={settings.max_history||16} onChange={e=>setSettings({...settings,max_history:Number(e.target.value)})}/></label>
        <label className="switch-row"><input type="checkbox" checked={!!settings.public_chat_enabled} onChange={e=>setSettings({...settings,public_chat_enabled:e.target.checked})}/><span><b>المحادثة العامة</b></span></label>
        <label className="switch-row"><input type="checkbox" checked={!!settings.verification_enabled} onChange={e=>setSettings({...settings,verification_enabled:e.target.checked})}/><span><b>Formal Verification</b></span></label>
        <label className="switch-row"><input type="checkbox" checked={!!settings.deep_reasoning_enabled} onChange={e=>setSettings({...settings,deep_reasoning_enabled:e.target.checked})}/><span><b>Deep Reasoning</b></span></label>
        <label>أقصى استدعاءات<input type="number" min="1" max="4" value={settings.max_model_calls_per_request||3} onChange={e=>setSettings({...settings,max_model_calls_per_request:Number(e.target.value)})}/></label>
      </div>}<div className="status-list" style={{marginTop:12}}><div><span>Paid external</span><b>مغلق</b></div><div><span>Daily paid budget</span><b>$0</b></div><div><span>Self-hosted</span><b>{status?.self_hosted_configured?'متصل':'غير موصول بعد'}</b></div></div><button className="primary-btn fit" onClick={saveRuntime} disabled={busy}>حفظ الإعدادات</button></div>

      <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">EVALUATION</span><h3>القياس المجاني</h3><p>يشغّل Benchmark واحدًا فقط مع zero-cost gate.</p></div></div><div className="status-list"><div><span>OpenRouter Free</span><b>{status?.openrouter_configured?'جاهز':'غير جاهز'}</b></div><div><span>Self-hosted AQLEVON</span><b>{status?.self_hosted_configured?'جاهز':'بانتظار GPU'}</b></div><div><span>Training candidates</span><b>{candidates.length}</b></div><div><span>Approved</span><b>{approved.length}</b></div></div><button className="primary-btn fit" onClick={runBenchmark} disabled={busy} style={{marginTop:14}}>تشغيل Benchmark واحد</button></div>
    </section>

    <section className="admin-panel wide" style={{marginTop:12}}><div className="panel-head"><div><span className="eyebrow">SECURE LEARNING GATE</span><h3>Traces المؤهلة للتعلم</h3><p>VERIFIED وحده لا يغيّر training set. الترقية تحتاج قرار المالك من هنا.</p></div></div><div className="table-list">{eligible.length?eligible.slice(0,40).map(x=>{const promoted=promotedIds.has(String(x.id));return <div className="table-row" key={x.id}><div><b>{domainNames[traceDomain(x)]||traceDomain(x)} · {x.difficulty||'—'}</b><span>{x.provider||'—'} · {x.model||'—'} · {x.model_calls||1} calls</span></div><span>{resultOf(x.verification)}</span><span>{x.latency_ms?`${x.latency_ms}ms`:'—'}</span><button className="primary-btn fit" disabled={busy||promoted} onClick={()=>promoteTrace(x.id)}>{promoted?'تمت الترقية':'ترقية للتعلم'}</button></div>}):<div className="empty-panel">لا توجد Traces VERIFIED مؤهلة حاليًا.</div>}</div></section>

    <section className="admin-panel wide" style={{marginTop:12}}><div className="panel-head"><div><span className="eyebrow">TRAINING REVIEW</span><h3>مراجعة Training Candidates</h3><p>لا يصبح المثال معتمدًا إلا بعد قرار المالك.</p></div></div><div className="table-list">{candidates.length?candidates.slice(0,50).map(x=><div className="table-row" key={x.id}><div><b>{String(x.user_input||'').slice(0,90)||'Training example'}</b><span>{(x.tags||[]).join(' · ')}</span></div><span>{x.quality_status}</span><div style={{display:'flex',gap:8}}><button className="primary-btn fit" disabled={busy} onClick={()=>reviewExample(x.id,'approved')}>اعتماد</button><button className="ghost-fit" disabled={busy} onClick={()=>reviewExample(x.id,'rejected')}>رفض</button></div></div>):<div className="empty-panel">لا توجد Candidates تنتظر المراجعة.</div>}</div></section>
  </main>;
}
