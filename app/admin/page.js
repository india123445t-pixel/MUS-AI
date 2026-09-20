'use client';

import {useEffect,useMemo,useالحالة} from 'react';
import {createClient} from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

const domainNames={reasoning:'الاستدلال',math:'الرياضيات',science:'العلوم',coding:'البرمجة',language:'اللغة',research:'البحث',planning:'التخطيط',knowledge:'المعرفة',general:'عام',software:'البرمجة',data:'البيانات',communication:'التواصل',operations:'العمليات'};
const safeModes=['openrouter_primary','openrouter_only','self_hosted_primary','self_hosted_only'];
const nav=[['owner','القيادة'],['missions','المهام'],['traces','التتبّع'],['incidents','الحوادث'],['overview','نظرة عامة'],['brain','ذاكرة المشروع'],['model_lab','مختبر النموذج'],['evaluation','التقييم'],['learning','التعلّم'],['infrastructure','البنية التحتية'],['security','الأمن المصرّح'],['runtime','التشغيل'],['access','الوصول والصلاحيات']];
const profiles=[
  ['guardian','الحارس','حراسة المشروع ومراقبة الحالة والانحرافات.'],
  ['engineer','المهندس','الكود، الإصلاح، الاختبارات، والبنية.'],
  ['model_lab','مختبر النموذج','الأوزان، الجينات، التجارب، والتقييم.'],
  ['research','البحث','البحث والتحليل واقتراح التجارب.'],
  ['authorized_security','الأمن المصرّح','اختبارات أمنية داخل الأصول المصرح بها في المهمة.'],
];
const phases={OPEN:'بانتظار الموافقة',READY:'موافق عليها',RUNNING:'قيد التنفيذ',WAITING:'متوقفة/بانتظار',RECONCILING:'تحقق ومصالحة',CLOSED:'مغلقة'};
const outcomes={NONE:'—',SUCCESS:'نجاح',PARTIAL:'جزئي',FAILED:'فشل',CANCELLED:'أوقفها المالك',UNKNOWN:'غير محسوم'};

function Metric({label,value,sub}){return <div className="metric-card"><span>{label}</span><strong>{value}</strong>{sub&&<small>{sub}</small>}</div>}
function resultOf(v){return String(v?.result||'').toUpperCase()}
function isموثّق(log){return resultOf(log?.verification)==='VERIFIED'}
function learningEligible(log){return isموثّق(log)&&log?.learning_eligible===true}
function traceDomain(log){return log?.task_contract?.primary_domain||log?.task_contract?.domain||'general'}
function freeالنموذج(v){const s=String(v||'openrouter/free').trim();return s==='openrouter/free'||s.endsWith(':free')?s:'openrouter/free'}
function when(v){if(!v)return '—';try{return new Date(v).toLocaleString('ar-MA')}catch{return '—'}}
function short(v,n=12){const s=String(v||'');return s.length>n?`${s.slice(0,n)}…`:s||'—'}
function phaseLabel(v){return phases[v]||v||'—'}
function outcomeLabel(v){return outcomes[v]||v||'—'}
function executorLabel(v){return ({LIVE:'مباشر',IDLE:'خامل','NOT CONNECTED':'غير متصل',NOT_CONNECTED:'غير متصل',CONNECTED:'متصل'})[v]||v||'—'}
function percentile(values,p){const xs=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!xs.length)return 0;const i=Math.min(xs.length-1,Math.max(0,Math.ceil((p/100)*xs.length)-1));return Math.round(xs[i])}

export default function AdminPage(){
  const sb=useMemo(()=>URL&&KEY?createClient(URL,KEY):null,[]);
  const [ready,setReady]=useالحالة(false),[session,setSession]=useالحالة(null),[authorized,setAuthorized]=useالحالة(false);
  const [email,setEmail]=useالحالة(''),[password,setPassword]=useالحالة(''),[authMsg,setAuthMsg]=useالحالة('');
  const [status,setStatus]=useالحالة(null),[settings,setSettings]=useالحالة(null),[logs,setLogs]=useالحالة([]),[examples,setExamples]=useالحالة([]),[bench,setBench]=useالحالة([]),[skills,setSkills]=useالحالة([]);
  const [tasks,setالمهام]=useالحالة([]),[intents,setالنية التنفيذيةs]=useالحالة([]),[attempts,setالمحاولات]=useالحالة([]),[receipts,setالإيصالات]=useالحالة([]),[audit,setالتدقيق]=useالحالة([]),[responses,setResponses]=useالحالة([]);
  const [busy,setBusy]=useالحالة(false),[notice,setNotice]=useالحالة(''),[tab,setTab]=useالحالة('owner');
  const [ownerBusy,setOwnerBusy]=useالحالة(false),[ownerInput,setOwnerInput]=useالحالة(''),[ownerالنمط,setOwnerالنمط]=useالحالة('guardian'),[ownerMode,setOwnerMode]=useالحالة('mission');
  const [ownerMessages,setOwnerMessages]=useالحالة([{role:'assistant',text:'أنا AQLEVON Owner Core. أعمل داخل لوحة المالك الخاصة. أستطيع تحليل المشروع وتحضير المهمة قابلة للموافقة، ولا أدّعي تنفيذ أي إجراء خارجي من دون التصريح/الإيصال فعلي.'}]);
  const [selectedTask,setSelectedTask]=useالحالة(null);
  const [selectedالمحاولة,setSelectedالمحاولة]=useالحالة(null);
  const [globalQuery,setGlobalQuery]=useالحالة('');
  const [traceFilter,setTraceFilter]=useالحالة('ALL');

  useEffect(()=>{
    if(!sb){setReady(true);return}
    sb.auth.getSession().then(({data})=>{setSession(data.session||null);setReady(true)});
    const {data}=sb.auth.onAuthالحالةChange((_event,s)=>setSession(s));
    return()=>data.subscription.unsubscribe();
  },[sb]);

  useEffect(()=>{if(session)loadAll();else setAuthorized(false)},[session]);

  async function login(e){e.preventDefault();setAuthMsg('');const r=await sb.auth.signInWithPassword({email,password});if(r.error)setAuthMsg('بيانات الدخول غير صحيحة.')}
  async function safeRows(promise){try{const r=await promise;return r.error?[]:(r.data||[])}catch{return []}}

  async function loadAll(){
    setBusy(true);setNotice('');
    try{
      const user=(await sb.auth.getUser()).data.user;
      if(!user)throw new Error('جلسة غير صالحة.');
      const owner=await sb.from('system_owner').select('owner_id').eq('owner_id',user.id).maybeSingle();
      if(owner.error||!owner.data){setAuthorized(false);await sb.auth.signOut();throw new Error('هذا الحساب غير مخول لإدارة AQLEVON.');}
      setAuthorized(true);
      const core=await Promise.all([
        fetch('/api/status',{cache:'no-store'}).then(r=>r.json()).catch(()=>null),
        sb.from('control_settings').select('*').eq('owner_id',user.id).single(),
        sb.from('public_chat_logs').select('id,created_at,task_contract,route_decision,verification,latency_ms,model_calls,difficulty,learning_eligible,model,provider').order('created_at',{ascending:false}).limit(120),
        sb.from('training_examples').select('id,user_input,preferred_answer,quality_status,tags,context_snapshot,created_at').order('created_at',{ascending:false}).limit(150),
        sb.from('benchmark_results').select('id,score,created_at,model_label,judge').order('created_at',{ascending:false}).limit(100),
        sb.from('skill_state').select('domain,score,attempts,wins').order('score',{ascending:true})
      ]);
      const [t,i,a,r,au,re]=await Promise.all([
        safeRows(sb.from('aqlevon_tasks').select('id,phase,outcome,title,scope,created_at,updated_at').order('updated_at',{ascending:false}).limit(40)),
        safeRows(sb.from('aqlevon_action_intents').select('id,task_id,semantic_action,canonical_resource,canonical_parameters,effective_capabilities,auth_state,created_at').order('created_at',{ascending:false}).limit(100)),
        safeRows(sb.from('aqlevon_action_attempts').select('id,task_id,action_intent_id,permit_id,attempt_no,phase,outcome,provider_operation_id,started_at,closed_at,created_at').order('created_at',{ascending:false}).limit(120)),
        safeRows(sb.from('aqlevon_action_receipts').select('id,action_attempt_id,action_intent_id,permit_id,executor_identity,transport_status,executor_reported_outcome,provider_operation_id,emitted_at').order('emitted_at',{ascending:false}).limit(120)),
        safeRows(sb.from('aqlevon_audit_events').select('id,task_id,event_type,subject_type,subject_ref,event_data,created_at').order('created_at',{ascending:false}).limit(180)),
        safeRows(sb.from('aqlevon_responses').select('id,task_id,response_type,body,metadata,emitted_at').order('emitted_at',{ascending:false}).limit(120))
      ]);
      setStatus(core[0]||null);setSettings(core[1].data||null);setLogs(core[2].data||[]);setExamples(core[3].data||[]);setBench(core[4].data||[]);setSkills(core[5].data||[]);
      setالمهام(t);setالنية التنفيذيةs(i);setالمحاولات(a);setالإيصالات(r);setالتدقيق(au);setResponses(re);
      if(!selectedTask&&t.length)setSelectedTask(t[0].id);
    }catch(e){setNotice(e?.message||'تعذر تحميل لوحة التحكم.')}finally{setBusy(false)}
  }

  async function saveRuntime(){
    if(!settings)return;setBusy(true);setNotice('');
    try{
      const mode=safeModes.includes(settings.runtime_mode)?settings.runtime_mode:'openrouter_primary';
      const patch={runtime_mode:mode,openrouter_model:freeالنموذج(settings.openrouter_model),temperature:Math.max(0,Math.min(2,Number(settings.temperature??0.6))),max_history:Math.max(4,Math.min(64,Number(settings.max_history||16))),public_chat_enabled:!!settings.public_chat_enabled,public_training_enabled:!!settings.public_training_enabled,save_training_candidates:!!settings.save_training_candidates,intelligence_router_enabled:!!settings.intelligence_router_enabled,verification_enabled:!!settings.verification_enabled,deep_reasoning_enabled:!!settings.deep_reasoning_enabled,max_model_calls_per_request:Math.max(1,Math.min(4,Number(settings.max_model_calls_per_request||3))),allow_paid_external:false,daily_budget_usd:0};
      const {error}=await sb.from('control_settings').update(patch).eq('owner_id',settings.owner_id);if(error)throw error;
      setNotice('تم حفظ إعدادات AQLEVON مع إبقاء الإنفاق المدفوع مقفلاً عند صفر.');await loadAll();
    }catch(e){setNotice(e?.message||'تعذر حفظ الإعدادات.')}finally{setBusy(false)}
  }

  async function runالتقييم(){if(!session)return;setBusy(true);setNotice('');try{const r=await fetch('/api/benchmark/run',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:'{}'});const d=await r.json();if(!r.ok)throw new Error(d.message||'فشل الاختبار.');setNotice(`التقييم ${domainNames[d.domain]||d.domain}: ${d.score}/100`);await loadAll()}catch(e){setNotice(e?.message||'فشل التقييم.')}finally{setBusy(false)}}
  async function promoteTrace(id){setBusy(true);setNotice('');try{const {data,error}=await sb.rpc('promote_verified_chat_to_training',{p_chat_log_id:id});if(error)throw error;setNotice(`تمت ترقية الـtrace إلى Training Candidate: ${data}`);await loadAll()}catch(e){setNotice(e?.message||'تعذر ترقية الـtrace.')}finally{setBusy(false)}}
  async function reviewExample(id,quality_status){setBusy(true);setNotice('');try{const {error}=await sb.from('training_examples').update({quality_status}).eq('id',id);if(error)throw error;setNotice(quality_status==='approved'?'تم اعتماد المثال.':'تم رفض المثال.');await loadAll()}catch(e){setNotice(e?.message||'تعذر تحديث المثال.')}finally{setBusy(false)}}

  async function ownerإرسال(e){
    e?.preventDefault?.();
    const input=ownerInput.trim();if(!input||!session||ownerBusy)return;
    const prior=ownerMessages.slice(-12).map(m=>({role:m.role,content:m.text}));
    setOwnerMessages(v=>[...v,{role:'user',text:input}]);setOwnerInput('');setOwnerBusy(true);setNotice('');
    try{
      const r=await fetch('/api/admin/owner-core/chat',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:JSON.stringify({input,history:prior,profile:ownerالنمط,mode:ownerMode})});
      const d=await r.json();if(!r.ok)throw new Error(d.message||'تعذر تشغيل Owner Core.');
      setOwnerMessages(v=>[...v,{role:'assistant',text:d.text||'تم إعداد الرد.',meta:{run_id:d.run_id,execution_state:d.execution_state}}]);
      if(d.task?.id)setSelectedTask(d.task.id);
      await loadAll();
    }catch(err){setOwnerMessages(v=>[...v,{role:'assistant',text:`تعذر إكمال الطلب: ${err?.message||'خطأ غير معروف'}`,error:true}])}finally{setOwnerBusy(false)}
  }

  async function taskAction(taskId,action){
    if(!session||!taskId)return;setBusy(true);setNotice('');
    try{
      const r=await fetch('/api/admin/owner-core/task',{method:'PATCH',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:JSON.stringify({task_id:taskId,action})});
      const d=await r.json();if(!r.ok)throw new Error(d.message||'تعذر تحديث المهمة.');setNotice(d.message||'تم تحديث المهمة.');await loadAll();
    }catch(e){setNotice(e?.message||'تعذر تحديث المهمة.')}finally{setBusy(false)}
  }

  if(!URL||!KEY)return <div className="center-screen"><div className="error-box">إعداد Supabase غير مكتمل.</div></div>;
  if(!ready)return <div className="center-screen"><div className="brand-loader"><img src="/admin-icon.svg" alt=""/><b>AQLEVON AI</b></div></div>;
  if(!session)return <div className="admin-login-shell"><form className="admin-login-card" onSubmit={login}><img src="/admin-icon.svg" alt="AQLEVON AI"/><span className="eyebrow">مركز التحكم الخاص</span><h1>AQLEVON AI</h1><div className="admin-version-badge">نواة المالك V3 · منصة التتبّع</div><p>لوحة الإدارة الخاصة بالمشروع.</p><label>البريد الإلكتروني<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>كلمة المرور<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label><button className="primary-btn" type="submit">دخول</button>{authMsg&&<div className="auth-msg">{authMsg}</div>}</form></div>;
  if(!authorized&&!busy)return <div className="center-screen"><div className="error-box">غير مصرح لهذا الحساب.</div></div>;

  const verified=logs.filter(isموثّق).length,eligible=logs.filter(learningEligible),promotedIds=new Set(examples.map(x=>x.context_snapshot?.public_chat_log_id).filter(Boolean).map(String));
  const candidates=examples.filter(x=>x.quality_status==='candidate'),approved=examples.filter(x=>x.quality_status==='approved');
  const avgBench=bench.length?(bench.reduce((a,x)=>a+Number(x.score||0),0)/bench.length).toFixed(1):'—',avgSkill=skills.length?(skills.reduce((a,x)=>a+Number(x.score||0),0)/skills.length).toFixed(0):'—';
  const pendingالمهام=tasks.filter(t=>t.phase==='OPEN'),runningالمهام=tasks.filter(t=>['READY','RUNNING','WAITING','RECONCILING'].includes(t.phase));
  const pendingالنية التنفيذيةs=intents.filter(i=>['PROPOSED','AWAITING_CONFIRMATION'].includes(i.auth_state));
  const نشطةTask=tasks.find(t=>t.id===selectedTask)||tasks[0]||null;
  const نشطةالمحاولات=نشطةTask?attempts.filter(a=>a.task_id===نشطةTask.id):[];
  const نشطةالتدقيق=نشطةTask?audit.filter(a=>a.task_id===نشطةTask.id).slice(0,18):audit.slice(0,18);
  const نشطةResponses=نشطةTask?responses.filter(r=>r.task_id===نشطةTask.id).slice(0,8):[];
  const نشطةالإيصالIds=new Set(نشطةالمحاولات.map(a=>a.id));
  const نشطةالإيصالات=receipts.filter(r=>نشطةالإيصالIds.has(r.action_attempt_id)).slice(0,8);
  const hasInFlight=نشطةالمحاولات.some(a=>a.phase==='IN_FLIGHT');
  const closedالمهام=tasks.filter(t=>t.phase==='CLOSED');
  const successfulالمهام=closedالمهام.filter(t=>t.outcome==='SUCCESS');
  const successRate=closedالمهام.length?Math.round(successfulالمهام.length/closedالمهام.length*100):0;
  const avgLatency=logs.length?Math.round(logs.reduce((sum,x)=>sum+Number(x.latency_ms||0),0)/logs.length):0;
  const evidenceCoverage=attempts.length?Math.min(100,Math.round(receipts.length/attempts.length*100)):0;
  const incidentCount=attempts.filter(a=>['FAILED','UNKNOWN'].includes(a.outcome)).length;
  const latestالنموذج=logs.find(x=>x.model)?.model||settings?.openrouter_model||'—';
  const executorالحالة=hasInFlight?'LIVE':attempts.length?'خامل':'NOT متصل';
  const latencyValues=logs.map(x=>Number(x.latency_ms||0)).filter(x=>x>0);
  const p50Latency=percentile(latencyValues,50),p95Latency=percentile(latencyValues,95),p99Latency=percentile(latencyValues,99);
  const terminalالمحاولات=attempts.filter(a=>['SUCCESS','PARTIAL','FAILED','CANCELLED'].includes(a.outcome));
  const toolنجاحRate=terminalالمحاولات.length?Math.round(terminalالمحاولات.filter(a=>a.outcome==='SUCCESS').length/terminalالمحاولات.length*100):0;
  const q=globalQuery.trim().toLowerCase();
  const filteredالمهام=tasks.filter(t=>!q||String(t.title||'').toLowerCase().includes(q)||String(t.id||'').toLowerCase().includes(q)||String(t.scope?.profile||'').toLowerCase().includes(q));
  const filteredالمحاولات=attempts.filter(a=>{
    const matchFilter=traceFilter==='ALL'||a.phase===traceFilter||a.outcome===traceFilter;
    const matchQuery=!q||[a.id,a.task_id,a.provider_operation_id,a.permit_id,a.phase,a.outcome].some(v=>String(v||'').toLowerCase().includes(q));
    return matchFilter&&matchQuery;
  });
  const نشطةالمحاولة=attempts.find(a=>a.id===selectedالمحاولة)||filteredالمحاولات[0]||null;
  const نشطةالمحاولةTask=نشطةالمحاولة?tasks.find(t=>t.id===نشطةالمحاولة.task_id):null;
  const نشطةالمحاولةالنية التنفيذية=نشطةالمحاولة?intents.find(i=>i.id===نشطةالمحاولة.action_intent_id):null;
  const نشطةالمحاولةالإيصال=نشطةالمحاولة?receipts.find(r=>r.action_attempt_id===نشطةالمحاولة.id):null;
  const نشطةالمحاولةالتدقيق=نشطةالمحاولة?audit.filter(e=>e.task_id===نشطةالمحاولة.task_id).slice(0,16):[];
  const securityالمهام=tasks.filter(t=>t.scope?.profile==='authorized_security');
  const sourceHealth=[
    ['Control Plane','متصل','المهام · intents · attempts · receipts'],
    ['Project التدقيق','متصل',`${audit.length} recent events loaded`],
    ['Evaluation Store','متصل',`${bench.length} benchmarks · ${verified} verified traces`],
    ['Learning Gate','متصل',`${candidates.length} candidates · ${approved.length} approved`],
    ['Git / Deploy / Browser','يحتاج موصل تنفيذ','التنفيذ bridge not connected'],
    ['Weights / Registry','PARTIAL','النموذج telemetry ظاهرة; lineage registry pending']
  ];

  return <div className="owner-admin-shell" dir="rtl">
    <aside className="owner-admin-sidebar">
      <div className="owner-brand"><img src="/admin-icon.svg" alt="AQLEVON"/><div><strong>AQLEVON</strong><span>تحكم المالك</span></div></div>
      <nav>
        <span className="owner-nav-kicker">التشغيل</span>
        {nav.filter(([id])=>['owner','missions','traces','incidents','overview'].includes(id)).map(([id,label])=><button key={id} className={tab===id?'نشطة':''} onClick={()=>setTab(id)}><span>{label}</span>{id==='owner'&&pendingالمهام.length>0?<b>{pendingالمهام.length}</b>:null}</button>)}
        <span className="owner-nav-kicker">الذكاء</span>
        {nav.filter(([id])=>['brain','model_lab','evaluation','learning'].includes(id)).map(([id,label])=><button key={id} className={tab===id?'نشطة':''} onClick={()=>setTab(id)}><span>{label}</span></button>)}
        <span className="owner-nav-kicker">النظام</span>
        {nav.filter(([id])=>['infrastructure','security','runtime','access'].includes(id)).map(([id,label])=><button key={id} className={tab===id?'نشطة':''} onClick={()=>setTab(id)}><span>{label}</span></button>)}
      </nav>
      <div className="owner-side-status"><span>صلاحية المالك</span><strong>نشط</strong><small>{session.user?.email||'system_owner'}</small></div>
      <div className="owner-side-actions"><a href="/" target="_blank">فتح التطبيق العام ↗</a><button onClick={()=>sb.auth.signOut()}>تسجيل الخروج</button></div>
    </aside>

    <main className="owner-admin-main">
      <header className="owner-admin-header v3-header">
        <div className="v3-title"><span className="eyebrow">AQLEVON · نواة المالك V3 · منصة التتبّع</span><h1>{nav.find(x=>x[0]===tab)?.[1]}</h1></div>
        <div className="v3-global-search"><span>⌕</span><input value={globalQuery} onChange={e=>setGlobalQuery(e.target.value)} placeholder="ابحث في المهام والتتبّعات والمعرّفات والمزوّدين…"/></div>
        <div className="header-actions">
          <span className="v3-env-pill">معاينة</span>
          <span className={`health-pill ${status?.openrouter_configured||status?.self_hosted_configured?'ok':'warn'}`}><i/>{status?.self_hosted_configured?'سيادي':status?.openrouter_configured?'بديل':'إعداد التشغيل'}</span>
          <button className="refresh-btn" onClick={loadAll} disabled={busy}>{busy?'…':'↻'}</button>
        </div>
      </header>
      {notice&&<div className="admin-notice">{notice}</div>}

      {tab==='owner'&&<>
        <section className="v3-command-head">
          <div><span className="eyebrow">نواة مالك AQLEVON V3 · منصة القيادة</span><h2>قيادة AQLEVON</h2><p>أرسل الأمر، راجع المهمة، وافق، ثم راقب التنفيذ والأدلة دون مغادرة نفس مساحة العمل.</p></div>
          <div className="v3-command-status">
            <span><i className={executorالحالة==='LIVE'?'live':''}/>{executorالحالة}</span>
            <span>{pendingالمهام.length+pendingالنية التنفيذيةs.length} بانتظار الموافقةs</span>
            <span>{incidentCount} incidents</span>
            <span>{evidenceCoverage}% evidence</span>
          </div>
        </section>

        <section className="command-workbench">
          <div className="command-chat-pane">
            <div className="command-pane-bar">
              <div><b>جلسة التشغيل</b><span>{session.user?.email||'system_owner'}</span></div>
              <div className="owner-inline-controls">
                <select value={ownerالنمط} onChange={e=>setOwnerالنمط(e.target.value)}>{profiles.map(x=><option key={x[0]} value={x[0]}>{x[1]}</option>)}</select>
                <select value={ownerMode} onChange={e=>setOwnerMode(e.target.value)}><option value="chat">تحليل</option><option value="mission">تحضير مهمة</option></select>
              </div>
            </div>
            <div className="command-context-bar"><span>النمط</span><b>{profiles.find(x=>x[0]===ownerالنمط)?.[1]}</b><small>{profiles.find(x=>x[0]===ownerالنمط)?.[2]}</small></div>
            <div className="command-chat-stream">
              {ownerMessages.map((m,i)=><div key={i} className={`command-message ${m.role} ${m.error?'error':''}`}><div className="command-message-meta"><span>{m.role==='user'?'OWNER':'AQLEVON'}</span>{m.meta&&<small>{m.meta.execution_state||'ADVISORY'} · {short(m.meta.run_id,8)}</small>}</div><p>{m.text}</p></div>)}
              {ownerBusy&&<div className="command-message assistant"><div className="command-message-meta"><span>AQLEVON</span></div><p>يتم تحضير الرد…</p></div>}
            </div>
            <form className="command-composer" onSubmit={ownerإرسال}>
              <textarea value={ownerInput} onChange={e=>setOwnerInput(e.target.value)} placeholder="أعط AQLEVON أمرًا، اطلب تحليل المشروع، أو حضّر المهمة للتنفيذ…" rows="3"/>
              <div><span>{ownerMode==='mission'?'تتطلب المهمة موافقة صريحة من المالك قبل أي تنفيذ خارجي.':'وضع استشاري · لا يتم إنشاء أو تعديل مهمة.'}</span><button className="primary-btn" disabled={ownerBusy||!ownerInput.trim()}>{ownerMode==='mission'?'تحضير مهمة':'إرسال'}</button></div>
            </form>
          </div>

          <aside className="command-control-rail">
            <div className="command-rail-head"><div><span className="eyebrow">التحكم بالمهام</span><h3>{نشطةTask?.title||'لم يتم اختيار مهمة'}</h3></div><span className={`v3-state-pill ${String(نشطةTask?.phase||'idle').toLowerCase()}`}>{نشطةTask?.phase||'خامل'}</span></div>
            <div className="command-queue">
              <div className="command-queue-title"><b>قائمة الانتظار</b><span>{tasks.length}</span></div>
              {tasks.length?tasks.slice(0,9).map(t=><button key={t.id} className={نشطةTask?.id===t.id?'نشطة':''} onClick={()=>setSelectedTask(t.id)}><div><b>{t.title||'AQLEVON المهمة'}</b><small>{short(t.id,12)} · {when(t.updated_at||t.created_at)}</small></div><span>{phaseLabel(t.phase)}</span></button>):<div className="empty-panel">لا توجد مهام بعد.</div>}
            </div>
            {نشطةTask&&<div className="command-mission-detail">
              <div className="v3-kv"><span>النتيجة</span><b>{نشطةTask.outcome}</b></div>
              <div className="v3-kv"><span>النمط</span><b>{نشطةTask.scope?.profile||'—'}</b></div>
              <div className="v3-kv"><span>الاستقلالية</span><b>{نشطةTask.scope?.autonomy||'بانتظار الموافقة_required'}</b></div>
              <div className="v3-kv"><span>المنفّذ</span><b>{نشطةTask.scope?.executor_state||'NOT_متصل'}</b></div>
              {نشطةTask.phase==='OPEN'&&<div className="v3-action-row"><button className="primary-btn" onClick={()=>taskAction(نشطةTask.id,'approve')} disabled={busy}>موافقة</button><button className="ghost-fit" onClick={()=>taskAction(نشطةTask.id,'cancel')} disabled={busy}>إلغاء</button></div>}
              <button className="owner-stop-btn" disabled={!hasInFlight} onClick={()=>taskAction(نشطةTask.id,'stop')}>إيقاف الآن</button>
            </div>}
          </aside>
        </section>

        <section className="command-lower-grid">
          <div className="command-live-pane">
            <div className="trace-pane-title"><b>التنفيذ المباشر</b><span>{hasInFlight?'LIVE':'NO نشط EXECUTOR'}</span></div>
            <div className="command-live-rows">
              {نشطةالمحاولات.length?نشطةالمحاولات.slice(0,12).map(a=><button key={a.id} onClick={()=>{setSelectedالمحاولة(a.id);setTab('traces')}}><span className={a.phase==='IN_FLIGHT'?'live-dot-cell':''}>{phaseLabel(a.phase)}</span><code>attempt #{a.attempt_no}</code><span>{short(a.provider_operation_id,18)}</span><b>{outcomeLabel(a.outcome)}</b></button>):<div className="command-empty-console">لا يوجد منفّذ خارجي متصل. ستظهر أنشطة الأدوات هنا فقط عند وجود محاولات تنفيذ حقيقية.</div>}
            </div>
          </div>
          <div className="command-audit-pane">
            <div className="trace-pane-title"><b>الأدلة وسجل التدقيق</b><button onClick={()=>setTab('traces')}>فتح التتبّع ↗</button></div>
            <div className="command-audit-list">{نشطةالتدقيق.length?نشطةالتدقيق.slice(0,10).map(e=><div key={e.id}><i/><div><b>{e.event_type}</b><small>{e.subject_type||'TASK'} · {when(e.created_at)}</small></div></div>):<div className="empty-panel">لا توجد أحداث تدقيق لهذه المهمة.</div>}</div>
          </div>
        </section>

        <section className="command-system-strip">
          <button onClick={()=>setTab('brain')}><span>ذاكرة المشروع</span><b>طبقة التحكم</b><small>{audit.length} audit events</small></button>
          <button onClick={()=>setTab('model_lab')}><span>النموذج</span><b>{short(latestالنموذج,22)}</b><small>{avgBench==='—'?'لا يوجد تقييم':avgBench+'/100 benchmark'}</small></button>
          <button onClick={()=>setTab('traces')}><span>المراقبة</span><b>P95 {p95Latency?p95Latency+'ms':'—'}</b><small>{toolنجاحRate}% نجاح الأدوات</small></button>
          <button onClick={()=>setTab('infrastructure')}><span>المنفّذs</span><b>{executorالحالة}</b><small>موصلات Git والمتصفح والنشر</small></button>
          <button onClick={()=>setTab('security')}><span>الأمن</span><b>ضمن نطاق مصرح فقط</b><small>{securityالمهام.length} مهام مصرّح بها</small></button>
        </section>
      </>}

      {tab==='missions'&&<>
        <section className="v3-section-head"><div><span className="eyebrow">سجل المهام</span><h2>مهام تحت سيطرة المالك</h2><p>المهام الحقيقية وحالتها وحدودها وقرارات المالك في سجل واحد.</p></div><div className="v3-head-stats"><span>{filteredالمهام.length} ظاهرة</span><span>{pendingالمهام.length} بانتظار الموافقة</span><span>{runningالمهام.length} نشطة</span></div></section>
        <section className="mission-workbench">
          <div className="mission-table-pane">
            <div className="v3-table-head mission-grid"><span>المهمة</span><span>المرحلة</span><span>النتيجة</span><span>النمط</span><span>المنفّذ</span><span>آخر تحديث</span></div>
            <div className="v3-scroll-list">{filteredالمهام.length?filteredالمهام.map(t=><button className={`v3-table-row mission-grid ${نشطةTask?.id===t.id?'selected':''}`} key={t.id} onClick={()=>setSelectedTask(t.id)}><span className="mission-title"><b>{t.title||'AQLEVON المهمة'}</b><small>{short(t.id,14)}</small></span><span>{phaseLabel(t.phase)}</span><span className={`tone-${String(t.outcome||'NONE').toLowerCase()}`}>{outcomeLabel(t.outcome)}</span><span>{t.scope?.profile||'—'}</span><span>{t.scope?.executor_state||'NOT_متصل'}</span><span>{when(t.updated_at||t.created_at)}</span></button>):<div className="empty-panel">لا توجد مهام تطابق البحث الحالي.</div>}</div>
          </div>
          <aside className="v3-inspector">
            <div className="v3-inspector-head"><span className="eyebrow">تفاصيل المهمة</span><h3>{نشطةTask?.title||'اختر مهمة'}</h3><small>{نشطةTask?.id||'—'}</small></div>
            {نشطةTask&&<>
              <div className="v3-kv"><span>المرحلة</span><b>{نشطةTask.phase}</b></div>
              <div className="v3-kv"><span>النتيجة</span><b>{نشطةTask.outcome}</b></div>
              <div className="v3-kv"><span>النمط</span><b>{نشطةTask.scope?.profile||'—'}</b></div>
              <div className="v3-kv"><span>الاستقلالية</span><b>{نشطةTask.scope?.autonomy||'بانتظار الموافقة_required'}</b></div>
              <div className="v3-kv"><span>المنفّذ</span><b>{نشطةTask.scope?.executor_state||'NOT_متصل'}</b></div>
              <div className="v3-divider"/>
              {نشطةTask.phase==='OPEN'&&<div className="v3-action-row"><button className="primary-btn" onClick={()=>taskAction(نشطةTask.id,'approve')} disabled={busy}>موافقة</button><button className="ghost-fit" onClick={()=>taskAction(نشطةTask.id,'cancel')} disabled={busy}>إلغاء</button></div>}
              <button className="owner-stop-btn" disabled={!hasInFlight} onClick={()=>taskAction(نشطةTask.id,'stop')}>إيقاف الآن</button>
              <div className="v3-subhead">الخط الزمني للأدلة</div>
              <div className="v3-event-list">{نشطةالتدقيق.length?نشطةالتدقيق.map(e=><div key={e.id}><i/><div><b>{e.event_type}</b><small>{when(e.created_at)}</small></div></div>):<span className="empty-inline">لا توجد أحداث تدقيق.</span>}</div>
            </>}
          </aside>
        </section>
      </>}

      {tab==='traces'&&<>
        <section className="trace-toolbar">
          <div><span className="eyebrow">مستكشف التتبّع</span><h2>مراقبة التنفيذ</h2></div>
          <div className="trace-metrics"><span>P50 <b>{p50Latency?p50Latency+'ms':'—'}</b></span><span>P95 <b>{p95Latency?p95Latency+'ms':'—'}</b></span><span>P99 <b>{p99Latency?p99Latency+'ms':'—'}</b></span><span>Tool success <b>{toolنجاحRate}%</b></span><span>المحاولات <b>{attempts.length}</b></span><span>الإيصالات <b>{receipts.length}</b></span></div>
          <select value={traceFilter} onChange={e=>setTraceFilter(e.target.value)}><option value="ALL">كل التتبّعات</option><option value="IN_FLIGHT">قيد التنفيذ</option><option value="CLOSED">أُغلق</option><option value="SUCCESS">نجاح</option><option value="FAILED">فشل</option><option value="UNKNOWN">غير محسوم</option></select>
        </section>
        <section className="trace-workbench">
          <div className="trace-list-pane">
            <div className="trace-pane-title"><b>التشغيلات</b><span>{filteredالمحاولات.length}</span></div>
            <div className="trace-run-list">{filteredالمحاولات.length?filteredالمحاولات.slice(0,80).map(a=><button key={a.id} className={نشطةالمحاولة?.id===a.id?'selected':''} onClick={()=>{setSelectedالمحاولة(a.id);setSelectedTask(a.task_id)}}><div><i className={a.phase==='IN_FLIGHT'?'live':''}/><b>{نشطةالمحاولةTask?.id===a.task_id?(نشطةالمحاولةTask?.title||'المهمة'):(tasks.find(t=>t.id===a.task_id)?.title||'المهمة')}</b></div><span>{phaseLabel(a.phase)} · {outcomeLabel(a.outcome)}</span><small>#{a.attempt_no} · {when(a.started_at||a.created_at)}</small></button>):<div className="empty-panel">لا توجد تتبّعات تنفيذ مسجلة بعد.</div>}</div>
          </div>
          <div className="trace-tree-pane">
            <div className="trace-pane-title"><b>تتبّع طبقة التحكم</b><span>{نشطةالمحاولة?short(نشطةالمحاولة.id,10):'—'}</span></div>
            {نشطةالمحاولة?<div className="trace-tree">
              <div className="trace-node root"><i/><div><span>MISSION</span><b>{نشطةالمحاولةTask?.title||'AQLEVON المهمة'}</b><small>{نشطةالمحاولة.task_id}</small></div></div>
              <div className="trace-node"><i/><div><span>INTENT</span><b>{نشطةالمحاولةالنية التنفيذية?.semantic_action||'Action intent'}</b><small>{نشطةالمحاولةالنية التنفيذية?.canonical_resource||'No canonical resource'}</small></div></div>
              <div className="trace-node نشطة"><i/><div><span>ATTEMPT</span><b>{نشطةالمحاولة.phase} · {نشطةالمحاولة.outcome}</b><small>{نشطةالمحاولة.provider_operation_id||'No provider operation id'}</small></div></div>
              <div className={`trace-node ${نشطةالمحاولةالإيصال?'verified':'muted'}`}><i/><div><span>RECEIPT</span><b>{نشطةالمحاولةالإيصال?.executor_reported_outcome||'No receipt yet'}</b><small>{نشطةالمحاولةالإيصال?.executor_identity||'الأدلة pending'}</small></div></div>
              {نشطةالمحاولةالتدقيق.slice(0,5).map(e=><div className="trace-node audit" key={e.id}><i/><div><span>AUDIT</span><b>{e.event_type}</b><small>{when(e.created_at)}</small></div></div>)}
            </div>:<div className="empty-panel">اختر تتبّعًا لعرض التفاصيل.</div>}
          </div>
          <aside className="trace-inspector">
            <div className="trace-pane-title"><b>التفاصيل</b><span>{نشطةالمحاولة?.phase||'—'}</span></div>
            {نشطةالمحاولة&&<>
              <div className="v3-inspector-tabs"><span className="نشطة">التفاصيل</span><span>الأدلة</span><span>التدقيق</span></div>
              <div className="v3-kv"><span>المحاولة</span><code>{نشطةالمحاولة.id}</code></div>
              <div className="v3-kv"><span>التصريح</span><code>{نشطةالمحاولة.permit_id||'—'}</code></div>
              <div className="v3-kv"><span>عملية المزوّد</span><code>{نشطةالمحاولة.provider_operation_id||'—'}</code></div>
              <div className="v3-kv"><span>بدأ</span><b>{when(نشطةالمحاولة.started_at||نشطةالمحاولة.created_at)}</b></div>
              <div className="v3-kv"><span>أُغلق</span><b>{when(نشطةالمحاولة.closed_at)}</b></div>
              <div className="v3-divider"/>
              <div className="v3-subhead">النية التنفيذية</div>
              <pre className="trace-json">{JSON.stringify({action:نشطةالمحاولةالنية التنفيذية?.semantic_action||null,resource:نشطةالمحاولةالنية التنفيذية?.canonical_resource||null,parameters:نشطةالمحاولةالنية التنفيذية?.canonical_parameters||null},null,2)}</pre>
              <div className="v3-subhead">الإيصال</div>
              <pre className="trace-json">{JSON.stringify(نشطةالمحاولةالإيصال?{executor:نشطةالمحاولةالإيصال.executor_identity,transport:نشطةالمحاولةالإيصال.transport_status,outcome:نشطةالمحاولةالإيصال.executor_reported_outcome,operation:نشطةالمحاولةالإيصال.provider_operation_id}:{status:'NO_RECEIPT'},null,2)}</pre>
            </>}
          </aside>
        </section>
        <section className="model-trace-strip">
          <div className="trace-pane-title"><b>النموذج traffic</b><span>{logs.length} تتبّعات حديثة</span></div>
          <div className="model-trace-table">{logs.slice(0,18).map(x=><div key={x.id}><span>{domainNames[traceDomain(x)]||traceDomain(x)}</span><b>{short(x.model,20)}</b><span>{x.latency_ms?x.latency_ms+'ms':'—'}</span><span>{x.model_calls||1} calls</span><span className={isموثّق(x)?'verified':''}>{resultOf(x.verification)||'UNVERIFIED'}</span></div>)}</div>
        </section>
      </>}

      {tab==='incidents'&&<>
        <section className="v3-section-head"><div><span className="eyebrow">مركز الحوادث</span><h2>الإخفاقات والتنفيذ غير المحسوم</h2><p>كل failure أو outcome غير محسوم يظهر هنا ليتحول من log مبعثر إلى مسار تحقيق واضح.</p></div><div className="v3-head-stats"><span>{incidentCount} إشارات مفتوحة</span><span>{attempts.filter(a=>a.outcome==='FAILED').length} فاشلة</span><span>{attempts.filter(a=>a.outcome==='UNKNOWN').length} غير محسومة</span></div></section>
        <section className="incident-console">
          <div className="incident-table">
            <div className="incident-head"><span>الخطورة</span><span>المهمة / المحاولة</span><span>الحالة</span><span>عملية المزوّد</span><span>الوقت</span></div>
            {attempts.filter(a=>['FAILED','UNKNOWN'].includes(a.outcome)).length?attempts.filter(a=>['FAILED','UNKNOWN'].includes(a.outcome)).map(a=><button key={a.id} onClick={()=>{setSelectedالمحاولة(a.id);setSelectedTask(a.task_id);setTab('traces')}}><span className={a.outcome==='FAILED'?'sev-high':'sev-warn'}>{a.outcome==='FAILED'?'HIGH':'REVIEW'}</span><span><b>{tasks.find(t=>t.id===a.task_id)?.title||'AQLEVON المهمة'}</b><small>{short(a.id,14)}</small></span><span>{phaseLabel(a.phase)} · {outcomeLabel(a.outcome)}</span><code>{short(a.provider_operation_id,18)}</code><span>{when(a.started_at||a.created_at)}</span></button>):<div className="empty-panel">No فاشلة or unresolved execution attempts.</div>}
          </div>
          <aside className="incident-guidance"><span className="eyebrow">سياسة المعالجة</span><h3>الأدلة before resolution</h3><p>لا نغلق Incident لأن executor قال “نجاح”. الإغلاق يعتمد على receipt + verification + audit trail.</p><div className="v3-kv"><span>الأدلة coverage</span><b>{evidenceCoverage}%</b></div><div className="v3-kv"><span>غير محسوم outcomes</span><b>{attempts.filter(a=>a.outcome==='UNKNOWN').length}</b></div><div className="v3-kv"><span>طلبات الإيقاف</span><b>{audit.filter(e=>e.event_type==='OWNER_STOP_REQUESTED').length}</b></div></aside>
        </section>
      </>}

      {tab==='brain'&&<>
        <section className="brain-hero">
          <div><span className="eyebrow">ذاكرة المشروع</span><h2>خريطة الحقيقة التشغيلية</h2><p>مصادر الحقيقة التي يعتمد عليها Owner Core الآن، وما هو موصول فعليًا وما زال يحتاج Adapter.</p></div>
          <div className="brain-score"><span>المصادر المتصلة</span><strong>{sourceHealth.filter(x=>x[1]==='متصل').length}/{sourceHealth.length}</strong></div>
        </section>
        <section className="brain-grid">
          {sourceHealth.map(([name,state,detail])=><div className="brain-source" key={name}><div><i className={state==='متصل'?'ok':state==='PARTIAL'?'warn':''}/><span>{name}</span></div><b>{state}</b><small>{detail}</small></div>)}
        </section>
        <section className="panel-grid">
          <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">القرارات الأخيرة</span><h3>التدقيق memory</h3></div></div><div className="owner-timeline">{audit.slice(0,18).map(e=><div key={e.id}><i/><div><b>{e.event_type}</b><span>{e.subject_type||'النظام'} · {when(e.created_at)}</span></div></div>)}</div></div>
          <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">مخرجات نواة المالك</span><h3>آخر الردود المحفوظة</h3></div></div><div className="brain-response-list">{responses.slice(0,12).map(r=><div key={r.id}><b>{r.response_type}</b><p>{String(r.body||'').slice(0,180)}</p><span>{when(r.emitted_at)}</span></div>)}</div></div>
        </section>
      </>}

      {tab==='model_lab'&&<>
        <section className="model-lab-hero">
          <div><span className="eyebrow">مختبر النموذج</span><h2>{short(latestالنموذج,34)}</h2><p>قياس الجودة، المهارات، traces، وحالة التعلم قبل أي ادعاء بتحسن النموذج.</p></div>
          <div className="model-lab-kpis"><div><span>التقييم</span><b>{avgBench==='—'?'—':avgBench+'/100'}</b></div><div><span>متوسط المهارات</span><b>{avgSkill==='—'?'—':avgSkill+'/100'}</b></div><div><span>موثّق</span><b>{verified}</b></div><div><span>موافقةd data</span><b>{approved.length}</b></div></div>
        </section>
        <section className="panel-grid">
          <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">خريطة القدرات</span><h3>حالة المهارات</h3></div></div><div className="skill-stack">{skills.slice(0,12).map(s=><div className="skill-line" key={s.domain}><div><span>{domainNames[s.domain]||s.domain}</span><b>{Number(s.score||0).toFixed(0)}</b></div><div><i style={{width:`${Math.max(2,Number(s.score)||0)}%`}}/></div></div>)}</div></div>
          <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">سجل التقييم</span><h3>نتائج التقييم الأخيرة</h3></div></div><div className="eval-list">{bench.slice(0,16).map(b=><div key={b.id}><div><b>{b.model_label||'AQLEVON'}</b><span>{when(b.created_at)}</span></div><strong>{Number(b.score||0).toFixed(1)}</strong><small>{b.judge||'judge'}</small></div>)}</div></div>
        </section>
      </>}

      {tab==='access'&&<>
        <section className="access-hero"><div><span className="eyebrow">الهوية والصلاحيات</span><h2>حدود التنفيذ تحت سيطرة المالك</h2><p>هوية المالك، مزودات التشغيل، وحدود الصلاحيات المستخدمة في المهام.</p></div><span className="access-owner-badge">النظام OWNER · نشط</span></section>
        <section className="access-grid">
          <div className="access-card connected"><span>هوية المالك</span><b>{session.user?.email||'system_owner'}</b><small>مصادقة Supabase + سجل مالك النظام</small></div>
          <div className="access-card connected"><span>طبقة تحكم Supabase</span><b>متصل</b><small>المصادقة · المهام · الإيصالات · التدقيق · التعلّم</small></div>
          <div className="access-card"><span>منفّذ Git / المستودع</span><b>NOT متصل</b><small>يلزم موصل تنفيذ قبل أي تعديل تلقائي للكود</small></div>
          <div className="access-card"><span>منفّذ المتصفح / الطرفية</span><b>NOT متصل</b><small>لا يتم الادعاء بأي تنفيذ خارجي غير موجود</small></div>
          <div className="access-card"><span>منفّذ النشر</span><b>NOT متصل</b><small>النشر يتطلب مهمة وافق عليها المالك صراحة</small></div>
          <div className="access-card warning"><span>الحوسبة المدفوعة</span><b>مقفلة</b><small>ميزانية التشغيل المدفوع اليومية الحالية: 0 دولار</small></div>
          <div className="access-card warning"><span>Authorized الأمن</span><b>ضمن نطاق مصرح فقط</b><small>يتطلب تحديد الهدف والنطاق صراحة داخل المهمة</small></div>
          <div className="access-card connected"><span>التدقيق evidence</span><b>{audit.length} أحداث</b><small>{receipts.length} execution receipts loaded</small></div>
        </section>
      </>}

      {tab==='overview'&&<><section className="metric-grid"><Metric label="الحالة" value={status?.openrouter_configured||status?.self_hosted_configured?'متصل':'يحتاج إعداد'} sub={settings?.runtime_mode||'—'}/><Metric label="موثّق" value={logs.length?`${Math.round(verified/logs.length*100)}%`:'—'} sub={`${verified} من ${logs.length}`}/><Metric label="التقييم" value={avgBench==='—'?'—':`${avgBench}/100`} sub={`${bench.length} نتائج`}/><Metric label="متوسط القدرات" value={avgSkill==='—'?'—':`${avgSkill}/100`} sub={`${skills.length} مجالات`}/><Metric label="المهمةs" value={tasks.length} sub={`${runningالمهام.length} نشطة`}/><Metric label="الإيصالات" value={receipts.length} sub="أدلة تنفيذ مسجلة"/></section><section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">الحالة الفعلية</span><h3>حالة النظام</h3></div></div><div className="status-list"><div><span>ذاتي الاستضافة</span><b>{status?.self_hosted_configured?'متصل':'غير موصول'}</b></div><div><span>وضع التشغيل</span><b>{settings?.runtime_mode||'—'}</b></div><div><span>Pending بانتظار الموافقةs</span><b>{pendingالمهام.length+pendingالنية التنفيذيةs.length}</b></div><div><span>إجراءات قيد التنفيذ</span><b>{attempts.filter(a=>a.phase==='IN_FLIGHT').length}</b></div></div></div><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">أضعف المهارات</span><h3>أضعف المجالات</h3></div></div><div className="skill-stack">{skills.slice(0,6).map(s=><div className="skill-line" key={s.domain}><div><span>{domainNames[s.domain]||s.domain}</span><b>{Number(s.score||0).toFixed(0)}</b></div><div><i style={{width:`${Math.max(2,Number(s.score)||0)}%`}}/></div></div>)}</div></div></section></>}

      {tab==='infrastructure'&&<>
        <section className="v3-section-head"><div><span className="eyebrow">البنية التحتية</span><h2>بيئة التشغيل والتنفيذ</h2><p>الحالة التي نعرفها فعليًا من النظام، مع فصل واضح بين المتصل وغير الموصول.</p></div></section>
        <section className="infra-matrix">
          <div className="infra-row"><div><i className="ok"/><b>طبقة تحكم Supabase</b></div><span>متصل</span><small>Auth · missions · receipts · audit · learning</small></div>
          <div className="infra-row"><div><i className={status?.openrouter_configured?'ok':'warn'}/><b>تشغيل OpenRouter</b></div><span>{status?.openrouter_configured?'مُعدّ':'NOT مُعدّ'}</span><small>{settings?.openrouter_model||'openrouter/free'}</small></div>
          <div className="infra-row"><div><i className={status?.self_hosted_configured?'ok':'warn'}/><b>AQLEVON ذاتي الاستضافة</b></div><span>{status?.self_hosted_configured?'متصل':'NOT متصل'}</span><small>{settings?.runtime_mode||'runtime mode غير محسومة'}</small></div>
          <div className="infra-row"><div><i/><b>منفّذ Git</b></div><span>يحتاج موصل تنفيذ</span><small>لا يوجد ادعاء بتنفيذ تلقائي على المستودع.</small></div>
          <div className="infra-row"><div><i/><b>المتصفح / الطرفية</b></div><span>يحتاج موصل تنفيذ</span><small>لا يوجد جسر عمليات خارجية مباشر متصل.</small></div>
          <div className="infra-row"><div><i/><b>منفّذ النشر</b></div><span>يحتاج موصل تنفيذ</span><small>موصل النشر بانتظار الربط ضمن موافقة المالك.</small></div>
          <div className="infra-row"><div><i/><b>قياس التكلفة والرموز</b></div><span>غير موصول بالقياس</span><small>لن تُعرض أرقام تكلفة أو رموز غير حقيقية قبل ربط القياس الفعلي.</small></div>
          <div className="infra-row"><div><i className="warn"/><b>الحوسبة المدفوعة</b></div><span>مقفلة</span><small>الميزانية المدفوعة اليومية: 0 دولار</small></div>
        </section>
      </>}

      {tab==='security'&&<>
        <section className="v3-section-head"><div><span className="eyebrow">الأمن المصرّح</span><h2>عمليات أمنية ضمن نطاق مصرح</h2><p>لا توجد صلاحية عامة: كل مهمة أمنية مرتبطة بهدف ونطاق مصرح به داخل المهمة.</p></div><span className="access-owner-badge">موافقة المالك مطلوبة</span></section>
        <section className="security-layout">
          <div className="security-policy">
            <div><span>تفويض الهدف</span><b>نطاق صريح فقط</b><small>يجب تحديد الأصول صراحة داخل نطاق المهمة.</small></div>
            <div><span>التنفيذ</span><b>{executorالحالة}</b><small>الأمن executor is not considered connected without a real adapter.</small></div>
            <div><span>الأدلة</span><b>{receipts.length} RECEIPTS</b><small>التنفيذ claims require recorded evidence.</small></div>
            <div><span>تحكم المالك</span><b>إلزامي</b><small>Scope expansion requires a new بانتظار الموافقة.</small></div>
          </div>
          <div className="admin-panel">
            <div className="panel-head"><div><span className="eyebrow">المهام الأمنية</span><h3>النطاقات المصرّح بها</h3></div></div>
            <div className="security-mission-list">{securityالمهام.length?securityالمهام.map(t=><button key={t.id} onClick={()=>{setSelectedTask(t.id);setTab('missions')}}><div><b>{t.title||'الأمن المهمة'}</b><small>{short(t.id,14)}</small></div><span>{phaseLabel(t.phase)} · {outcomeLabel(t.outcome)}</span></button>):<div className="empty-panel">لا توجد مهام أمنية مصرّح بها مسجلة.</div>}</div>
          </div>
        </section>
      </>}

      {tab==='runtime'&&<section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">التشغيل</span><h3>المحرك والسياسة</h3><p>الإنفاق المدفوع مقفول في هذه المرحلة.</p></div></div>{settings&&<div className="form-grid"><label>وضع التشغيل<select value={settings.runtime_mode||'openrouter_primary'} onChange={e=>setSettings({...settings,runtime_mode:e.target.value})}><option value="openrouter_primary">OpenRouter المجاني أولًا</option><option value="openrouter_only">OpenRouter المجاني فقط</option><option value="self_hosted_primary">AQLEVON ذاتي الاستضافة أولًا</option><option value="self_hosted_only">AQLEVON ذاتي الاستضافة فقط</option></select></label><label>نموذج OpenRouter المجاني<input value={settings.openrouter_model||'openrouter/free'} onChange={e=>setSettings({...settings,openrouter_model:e.target.value})}/></label><label>Temperature<input type="number" min="0" max="2" step="0.1" value={settings.temperature??0.6} onChange={e=>setSettings({...settings,temperature:Number(e.target.value)})}/></label><label>سياق المحادثة<input type="number" min="4" max="64" value={settings.max_history||16} onChange={e=>setSettings({...settings,max_history:Number(e.target.value)})}/></label><label className="switch-row"><input type="checkbox" checked={!!settings.verification_enabled} onChange={e=>setSettings({...settings,verification_enabled:e.target.checked})}/><span><b>التحقق الرسمي</b></span></label><label className="switch-row"><input type="checkbox" checked={!!settings.deep_reasoning_enabled} onChange={e=>setSettings({...settings,deep_reasoning_enabled:e.target.checked})}/><span><b>الاستدلال العميق</b></span></label></div>}<div className="status-list"><div><span>تشغيل خارجي مدفوع</span><b>مغلق</b></div><div><span>الميزانية المدفوعة اليومية</span><b>$0</b></div><div><span>ذاتي الاستضافة</span><b>{status?.self_hosted_configured?'متصل':'غير موصول بعد'}</b></div></div><button className="primary-btn fit" onClick={saveRuntime} disabled={busy}>حفظ الإعدادات</button></div><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">OPERATIONS</span><h3>حقيقة تنفيذ الإجراءات</h3></div></div><div className="status-list"><div><span>المهام</span><b>{tasks.length}</b></div><div><span>نيات التنفيذ</span><b>{intents.length}</b></div><div><span>المحاولات</span><b>{attempts.length}</b></div><div><span>الإيصالات</span><b>{receipts.length}</b></div></div></div></section>}

      {tab==='evaluation'&&<><section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">التقييم</span><h3>القياس المجاني</h3><p>يشغّل التقييم واحدًا فقط مع zero-cost gate.</p></div></div><div className="status-list"><div><span>OpenRouter المجاني</span><b>{status?.openrouter_configured?'جاهز':'غير جاهز'}</b></div><div><span>AQLEVON ذاتي الاستضافة</span><b>{status?.self_hosted_configured?'جاهز':'بانتظار GPU'}</b></div><div><span>مرشحات التدريب</span><b>{candidates.length}</b></div><div><span>موافقةd</span><b>{approved.length}</b></div></div><button className="primary-btn fit" onClick={runالتقييم} disabled={busy}>تشغيل التقييم واحد</button></div><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">التحقق</span><h3>الحقيقة قبل الترقية</h3></div></div><div className="status-list"><div><span>موثّق traces</span><b>{verified}</b></div><div><span>مؤهلة للتعلم</span><b>{eligible.length}</b></div><div><span>الأدلة receipts</span><b>{receipts.length}</b></div><div><span>محاولات غير محسومة</span><b>{attempts.filter(a=>a.outcome==='UNKNOWN').length}</b></div></div></div></section></>}

      {tab==='learning'&&<><section className="admin-panel wide"><div className="panel-head"><div><span className="eyebrow">بوابة التعلم الآمن</span><h3>Traces المؤهلة للتعلم</h3><p>VERIFIED وحده لا يغيّر training set. الترقية تحتاج قرار المالك من هنا.</p></div></div><div className="table-list">{eligible.length?eligible.slice(0,40).map(x=>{const promoted=promotedIds.has(String(x.id));return <div className="table-row" key={x.id}><div><b>{domainNames[traceDomain(x)]||traceDomain(x)} · {x.difficulty||'—'}</b><span>{x.provider||'—'} · {x.model||'—'} · {x.model_calls||1} calls</span></div><span>{resultOf(x.verification)}</span><span>{x.latency_ms?`${x.latency_ms}ms`:'—'}</span><button className="primary-btn fit" disabled={busy||promoted} onClick={()=>promoteTrace(x.id)}>{promoted?'تمت الترقية':'ترقية للتعلم'}</button></div>}):<div className="empty-panel">لا توجد Traces VERIFIED مؤهلة حاليًا.</div>}</div></section><section className="admin-panel wide"><div className="panel-head"><div><span className="eyebrow">مراجعة التدريب</span><h3>مراجعة Training Candidates</h3><p>لا يصبح المثال معتمدًا إلا بعد قرار المالك.</p></div></div><div className="table-list">{candidates.length?candidates.slice(0,50).map(x=><div className="table-row" key={x.id}><div><b>{String(x.user_input||'').slice(0,90)||'Training example'}</b><span>{(x.tags||[]).join(' · ')}</span></div><span>{x.quality_status}</span><div style={{display:'flex',gap:8}}><button className="primary-btn fit" disabled={busy} onClick={()=>reviewExample(x.id,'approved')}>اعتماد</button><button className="ghost-fit" disabled={busy} onClick={()=>reviewExample(x.id,'rejected')}>رفض</button></div></div>):<div className="empty-panel">لا توجد Candidates تنتظر المراجعة.</div>}</div></section></>}
    </main>
  </div>;
}