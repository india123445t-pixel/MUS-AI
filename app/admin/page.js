'use client';

import {useEffect,useMemo,useState} from 'react';
import {createClient} from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

const domainNames={reasoning:'الاستدلال',math:'الرياضيات',science:'العلوم',coding:'البرمجة',language:'اللغة',research:'البحث',planning:'التخطيط',knowledge:'المعرفة',general:'عام',software:'البرمجة',data:'البيانات',communication:'التواصل',operations:'العمليات'};
const safeModes=['openrouter_primary','openrouter_only','self_hosted_primary','self_hosted_only'];
const nav=[['owner','Owner Core'],['overview','نظرة عامة'],['runtime','المحرك'],['evaluation','التقييم'],['learning','التعلم']];
const profiles=[
  ['guardian','Guardian','حراسة المشروع ومراقبة الحالة والانحرافات.'],
  ['engineer','Engineer','الكود، الإصلاح، الاختبارات، والبنية.'],
  ['model_lab','Model Lab','الأوزان، الجينات، التجارب، والتقييم.'],
  ['research','Research','البحث والتحليل واقتراح التجارب.'],
  ['authorized_security','Authorized Security','اختبارات أمنية داخل الأصول المصرح بها في المهمة.'],
];
const phases={OPEN:'بانتظار الموافقة',READY:'موافق عليها',RUNNING:'قيد التنفيذ',WAITING:'متوقفة/بانتظار',RECONCILING:'تحقق ومصالحة',CLOSED:'مغلقة'};
const outcomes={NONE:'—',SUCCESS:'نجاح',PARTIAL:'جزئي',FAILED:'فشل',CANCELLED:'أوقفها المالك',UNKNOWN:'غير محسوم'};

function Metric({label,value,sub}){return <div className="metric-card"><span>{label}</span><strong>{value}</strong>{sub&&<small>{sub}</small>}</div>}
function resultOf(v){return String(v?.result||'').toUpperCase()}
function isVerified(log){return resultOf(log?.verification)==='VERIFIED'}
function learningEligible(log){return isVerified(log)&&log?.learning_eligible===true}
function traceDomain(log){return log?.task_contract?.primary_domain||log?.task_contract?.domain||'general'}
function freeModel(v){const s=String(v||'openrouter/free').trim();return s==='openrouter/free'||s.endsWith(':free')?s:'openrouter/free'}
function when(v){if(!v)return '—';try{return new Date(v).toLocaleString('ar-MA')}catch{return '—'}}
function short(v,n=12){const s=String(v||'');return s.length>n?`${s.slice(0,n)}…`:s||'—'}

export default function AdminPage(){
  const sb=useMemo(()=>URL&&KEY?createClient(URL,KEY):null,[]);
  const [ready,setReady]=useState(false),[session,setSession]=useState(null),[authorized,setAuthorized]=useState(false);
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[authMsg,setAuthMsg]=useState('');
  const [status,setStatus]=useState(null),[settings,setSettings]=useState(null),[logs,setLogs]=useState([]),[examples,setExamples]=useState([]),[bench,setBench]=useState([]),[skills,setSkills]=useState([]);
  const [tasks,setTasks]=useState([]),[intents,setIntents]=useState([]),[attempts,setAttempts]=useState([]),[receipts,setReceipts]=useState([]),[audit,setAudit]=useState([]),[responses,setResponses]=useState([]);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[tab,setTab]=useState('owner');
  const [ownerBusy,setOwnerBusy]=useState(false),[ownerInput,setOwnerInput]=useState(''),[ownerProfile,setOwnerProfile]=useState('guardian'),[ownerMode,setOwnerMode]=useState('mission');
  const [ownerMessages,setOwnerMessages]=useState([{role:'assistant',text:'أنا AQLEVON Owner Core. أعمل داخل لوحة المالك الخاصة. أستطيع تحليل المشروع وتحضير Mission قابلة للموافقة، ولا أدّعي تنفيذ أي إجراء خارجي من دون Permit/Receipt فعلي.'}]);
  const [selectedTask,setSelectedTask]=useState(null);

  useEffect(()=>{
    if(!sb){setReady(true);return}
    sb.auth.getSession().then(({data})=>{setSession(data.session||null);setReady(true)});
    const {data}=sb.auth.onAuthStateChange((_event,s)=>setSession(s));
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
      setTasks(t);setIntents(i);setAttempts(a);setReceipts(r);setAudit(au);setResponses(re);
      if(!selectedTask&&t.length)setSelectedTask(t[0].id);
    }catch(e){setNotice(e?.message||'تعذر تحميل لوحة التحكم.')}finally{setBusy(false)}
  }

  async function saveRuntime(){
    if(!settings)return;setBusy(true);setNotice('');
    try{
      const mode=safeModes.includes(settings.runtime_mode)?settings.runtime_mode:'openrouter_primary';
      const patch={runtime_mode:mode,openrouter_model:freeModel(settings.openrouter_model),temperature:Math.max(0,Math.min(2,Number(settings.temperature??0.6))),max_history:Math.max(4,Math.min(64,Number(settings.max_history||16))),public_chat_enabled:!!settings.public_chat_enabled,public_training_enabled:!!settings.public_training_enabled,save_training_candidates:!!settings.save_training_candidates,intelligence_router_enabled:!!settings.intelligence_router_enabled,verification_enabled:!!settings.verification_enabled,deep_reasoning_enabled:!!settings.deep_reasoning_enabled,max_model_calls_per_request:Math.max(1,Math.min(4,Number(settings.max_model_calls_per_request||3))),allow_paid_external:false,daily_budget_usd:0};
      const {error}=await sb.from('control_settings').update(patch).eq('owner_id',settings.owner_id);if(error)throw error;
      setNotice('تم حفظ إعدادات AQLEVON مع إبقاء الإنفاق المدفوع مقفلاً عند صفر.');await loadAll();
    }catch(e){setNotice(e?.message||'تعذر حفظ الإعدادات.')}finally{setBusy(false)}
  }

  async function runBenchmark(){if(!session)return;setBusy(true);setNotice('');try{const r=await fetch('/api/benchmark/run',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:'{}'});const d=await r.json();if(!r.ok)throw new Error(d.message||'فشل الاختبار.');setNotice(`Benchmark ${domainNames[d.domain]||d.domain}: ${d.score}/100`);await loadAll()}catch(e){setNotice(e?.message||'فشل Benchmark.')}finally{setBusy(false)}}
  async function promoteTrace(id){setBusy(true);setNotice('');try{const {data,error}=await sb.rpc('promote_verified_chat_to_training',{p_chat_log_id:id});if(error)throw error;setNotice(`تمت ترقية الـtrace إلى Training Candidate: ${data}`);await loadAll()}catch(e){setNotice(e?.message||'تعذر ترقية الـtrace.')}finally{setBusy(false)}}
  async function reviewExample(id,quality_status){setBusy(true);setNotice('');try{const {error}=await sb.from('training_examples').update({quality_status}).eq('id',id);if(error)throw error;setNotice(quality_status==='approved'?'تم اعتماد المثال.':'تم رفض المثال.');await loadAll()}catch(e){setNotice(e?.message||'تعذر تحديث المثال.')}finally{setBusy(false)}}

  async function ownerSend(e){
    e?.preventDefault?.();
    const input=ownerInput.trim();if(!input||!session||ownerBusy)return;
    const prior=ownerMessages.slice(-12).map(m=>({role:m.role,content:m.text}));
    setOwnerMessages(v=>[...v,{role:'user',text:input}]);setOwnerInput('');setOwnerBusy(true);setNotice('');
    try{
      const r=await fetch('/api/admin/owner-core/chat',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:JSON.stringify({input,history:prior,profile:ownerProfile,mode:ownerMode})});
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
  if(!ready)return <div className="center-screen"><div className="brand-loader"><img src="/icon.svg" alt=""/><b>AQLEVON AI</b></div></div>;
  if(!session)return <div className="admin-login-shell"><form className="admin-login-card" onSubmit={login}><img src="/icon.svg" alt="AQLEVON AI"/><span className="eyebrow">PRIVATE CONTROL CENTER</span><h1>AQLEVON AI</h1><p>لوحة الإدارة الخاصة بالمشروع.</p><label>البريد الإلكتروني<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>كلمة المرور<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label><button className="primary-btn" type="submit">دخول</button>{authMsg&&<div className="auth-msg">{authMsg}</div>}</form></div>;
  if(!authorized&&!busy)return <div className="center-screen"><div className="error-box">غير مصرح لهذا الحساب.</div></div>;

  const verified=logs.filter(isVerified).length,eligible=logs.filter(learningEligible),promotedIds=new Set(examples.map(x=>x.context_snapshot?.public_chat_log_id).filter(Boolean).map(String));
  const candidates=examples.filter(x=>x.quality_status==='candidate'),approved=examples.filter(x=>x.quality_status==='approved');
  const avgBench=bench.length?(bench.reduce((a,x)=>a+Number(x.score||0),0)/bench.length).toFixed(1):'—',avgSkill=skills.length?(skills.reduce((a,x)=>a+Number(x.score||0),0)/skills.length).toFixed(0):'—';
  const pendingTasks=tasks.filter(t=>t.phase==='OPEN'),runningTasks=tasks.filter(t=>['READY','RUNNING','WAITING','RECONCILING'].includes(t.phase));
  const pendingIntents=intents.filter(i=>['PROPOSED','AWAITING_CONFIRMATION'].includes(i.auth_state));
  const activeTask=tasks.find(t=>t.id===selectedTask)||tasks[0]||null;
  const activeAttempts=activeTask?attempts.filter(a=>a.task_id===activeTask.id):[];
  const activeAudit=activeTask?audit.filter(a=>a.task_id===activeTask.id).slice(0,18):audit.slice(0,18);
  const activeResponses=activeTask?responses.filter(r=>r.task_id===activeTask.id).slice(0,8):[];
  const activeReceiptIds=new Set(activeAttempts.map(a=>a.id));
  const activeReceipts=receipts.filter(r=>activeReceiptIds.has(r.action_attempt_id)).slice(0,8);
  const hasInFlight=activeAttempts.some(a=>a.phase==='IN_FLIGHT');

  return <div className="owner-admin-shell" dir="rtl">
    <aside className="owner-admin-sidebar">
      <div className="owner-brand"><img src="/icon.svg" alt="AQLEVON"/><div><strong>AQLEVON</strong><span>OWNER CONTROL</span></div></div>
      <nav>{nav.map(([id,label])=><button key={id} className={tab===id?'active':''} onClick={()=>setTab(id)}>{label}{id==='owner'&&pendingTasks.length>0?<b>{pendingTasks.length}</b>:null}</button>)}</nav>
      <div className="owner-side-status"><span>Owner authority</span><strong>ACTIVE</strong><small>{session.user?.email||'system_owner'}</small></div>
      <div className="owner-side-actions"><a href="/" target="_blank">فتح التطبيق العام ↗</a><button onClick={()=>sb.auth.signOut()}>تسجيل الخروج</button></div>
    </aside>

    <main className="owner-admin-main">
      <header className="owner-admin-header"><div><span className="eyebrow">PRIVATE · SYSTEM OWNER</span><h1>{nav.find(x=>x[0]===tab)?.[1]}</h1></div><div className="header-actions"><span className={`health-pill ${status?.openrouter_configured||status?.self_hosted_configured?'ok':'warn'}`}><i/>{status?.self_hosted_configured?'Sovereign ready':status?.openrouter_configured?'Fallback connected':'Runtime needs setup'}</span><button className="refresh-btn" onClick={loadAll} disabled={busy}>{busy?'…':'تحديث'}</button></div></header>
      {notice&&<div className="admin-notice">{notice}</div>}

      {tab==='owner'&&<>
        <section className="owner-command-strip">
          <div><span className="eyebrow">AQLEVON OWNER CORE</span><h2>مديرك الرقمي داخل المشروع</h2><p>ناقش، حضّر Mission، راقب التنفيذ الحقيقي، ووافق على الأفعال المؤثرة من مكان واحد.</p></div>
          <div className="owner-strip-metrics"><div><span>Pending approvals</span><b>{pendingTasks.length+pendingIntents.length}</b></div><div><span>Active missions</span><b>{runningTasks.length}</b></div><div><span>In-flight actions</span><b>{attempts.filter(a=>a.phase==='IN_FLIGHT').length}</b></div></div>
        </section>

        <section className="owner-core-grid">
          <div className="owner-chat-card">
            <div className="owner-card-head"><div><span className="eyebrow">OPERATOR CHAT</span><h3>تحدث مع AQLEVON</h3></div><div className="owner-inline-controls"><select value={ownerProfile} onChange={e=>setOwnerProfile(e.target.value)}>{profiles.map(p=><option key={p[0]} value={p[0]}>{p[1]}</option>)}</select><select value={ownerMode} onChange={e=>setOwnerMode(e.target.value)}><option value="chat">نقاش / تحليل</option><option value="mission">حضّر Mission للموافقة</option></select></div></div>
            <div className="owner-profile-note">{profiles.find(p=>p[0]===ownerProfile)?.[2]}</div>
            <div className="owner-chat-stream">{ownerMessages.map((m,i)=><div key={i} className={`owner-msg ${m.role} ${m.error?'error':''}`}><span>{m.role==='user'?'أنت':'AQLEVON'}</span><p>{m.text}</p>{m.meta&&<small>{m.meta.execution_state||'ADVISORY'} · {short(m.meta.run_id,8)}</small>}</div>)}{ownerBusy&&<div className="owner-msg assistant"><span>AQLEVON</span><p>يفكر ويجهز الرد…</p></div>}</div>
            <form className="owner-composer" onSubmit={ownerSend}><textarea value={ownerInput} onChange={e=>setOwnerInput(e.target.value)} placeholder="مثال: افحص حالة المشروع، اقترح ما يجب إصلاحه، أو حضّر مهمة محددة للموافقة…" rows="3"/><div><span>{ownerMode==='mission'?'سيتم إنشاء Mission بانتظار موافقتك، ولن يُدّعى أي تنفيذ قبل Receipt فعلي.':'وضع تحليلي بدون إنشاء Mission.'}</span><button className="primary-btn" disabled={ownerBusy||!ownerInput.trim()}>{ownerMode==='mission'?'حضّر المهمة':'إرسال'}</button></div></form>
          </div>

          <div className="owner-mission-card">
            <div className="owner-card-head"><div><span className="eyebrow">MISSION CONTROL</span><h3>الموافقات والمهام</h3></div><span className="state-badge">{pendingTasks.length} pending</span></div>
            <div className="owner-task-list">{tasks.length?tasks.slice(0,14).map(t=><button key={t.id} className={activeTask?.id===t.id?'active':''} onClick={()=>setSelectedTask(t.id)}><div><b>{t.title||'AQLEVON Mission'}</b><small>{when(t.updated_at||t.created_at)}</small></div><span>{phases[t.phase]||t.phase}</span></button>):<div className="empty-panel">لا توجد Missions بعد.</div>}</div>
            {activeTask&&<div className="owner-task-detail"><div className="owner-task-status"><b>{activeTask.title||'AQLEVON Mission'}</b><span>{phases[activeTask.phase]||activeTask.phase} · {outcomes[activeTask.outcome]||activeTask.outcome}</span></div><div className="owner-scope-row"><span>Profile</span><b>{activeTask.scope?.profile||'—'}</b></div><div className="owner-scope-row"><span>Autonomy</span><b>{activeTask.scope?.autonomy||'approval_required'}</b></div><div className="owner-scope-row"><span>Executor</span><b>{activeTask.scope?.executor_state||'NOT_CONNECTED'}</b></div>{activeTask.phase==='OPEN'&&<div className="owner-approval-actions"><button className="primary-btn" onClick={()=>taskAction(activeTask.id,'approve')} disabled={busy}>Approve Mission</button><button className="ghost-fit" onClick={()=>taskAction(activeTask.id,'cancel')} disabled={busy}>رفض / إلغاء</button></div>}<button className="owner-stop-btn" disabled={!hasInFlight} title={hasInFlight?'إرسال طلب إيقاف إلى executor المتصل':'لا يوجد تنفيذ خارجي In-Flight حاليًا'} onClick={()=>taskAction(activeTask.id,'stop')}>STOP NOW</button></div>}
          </div>
        </section>

        <section className="owner-workspace-grid">
          <div className="owner-workspace-panel"><div className="owner-card-head"><div><span className="eyebrow">LIVE WORKSPACE</span><h3>ما الذي يحدث فعليًا؟</h3></div><span className={`state-badge ${hasInFlight?'live':''}`}>{hasInFlight?'LIVE':'NO ACTIVE EXECUTOR'}</span></div><div className="owner-workspace-tabs"><span>Terminal</span><span>Browser</span><span>Files / Diff</span><span>Model</span><span>Security</span></div><div className="owner-terminal">{activeAttempts.length?activeAttempts.slice(0,10).map(a=><div key={a.id}><span>{a.phase}</span><code>attempt #{a.attempt_no} · {short(a.provider_operation_id,18)}</code><b>{a.outcome}</b></div>):<p>لا توجد عملية executor حية. عندما يُربط Tool Adapter وتبدأ ActionAttempt حقيقية ستظهر هنا بدل أي محاكاة.</p>}</div></div>
          <div className="owner-timeline-panel"><div className="owner-card-head"><div><span className="eyebrow">MISSION TIMELINE</span><h3>Evidence & Audit</h3></div></div><div className="owner-timeline">{activeAudit.length?activeAudit.map(e=><div key={e.id}><i/><div><b>{e.event_type}</b><span>{e.subject_type||'TASK'} · {when(e.created_at)}</span></div></div>):<div className="empty-panel">لا توجد أحداث تدقيق لهذه المهمة.</div>}</div>{activeReceipts.length>0&&<div className="owner-receipts"><b>Receipts</b>{activeReceipts.map(r=><span key={r.id}>{r.executor_identity} · {r.executor_reported_outcome||'UNKNOWN'} · {short(r.id,8)}</span>)}</div>}{activeResponses.length>0&&<div className="owner-receipts"><b>Agent responses</b>{activeResponses.map(r=><span key={r.id}>{r.response_type} · {String(r.body||'').slice(0,90)}</span>)}</div>}</div>
        </section>

        <section className="owner-identity-panel"><div><span className="eyebrow">IDENTITY & ACCESS</span><h3>AQLEVON operational identity</h3><p>الحسابات والتكاملات التنفيذية تُربط عبر scoped service identities/OAuth. الأسرار نفسها لا تظهر في الشات.</p></div><div className="owner-identity-grid"><div><span>Project Brain</span><b>CONTROL-PLANE CONNECTED</b><small>Tasks · receipts · evaluations · audit</small></div><div><span>Git / Deploy / Browser</span><b>ADAPTER REQUIRED</b><small>لا ندّعي اتصالًا غير موجود</small></div><div><span>Paid compute</span><b>OWNER APPROVAL REQUIRED</b><small>لا تفويض ضمني للإنفاق</small></div><div><span>Security mode</span><b>AUTHORIZED SCOPE ONLY</b><small>الأصول المحددة في Mission</small></div></div></section>
      </>}

      {tab==='overview'&&<><section className="metric-grid"><Metric label="الحالة" value={status?.openrouter_configured||status?.self_hosted_configured?'متصل':'يحتاج إعداد'} sub={settings?.runtime_mode||'—'}/><Metric label="Verified" value={logs.length?`${Math.round(verified/logs.length*100)}%`:'—'} sub={`${verified} من ${logs.length}`}/><Metric label="Benchmark" value={avgBench==='—'?'—':`${avgBench}/100`} sub={`${bench.length} نتائج`}/><Metric label="متوسط القدرات" value={avgSkill==='—'?'—':`${avgSkill}/100`} sub={`${skills.length} مجالات`}/><Metric label="Missions" value={tasks.length} sub={`${runningTasks.length} نشطة`}/><Metric label="Receipts" value={receipts.length} sub="أدلة تنفيذ مسجلة"/></section><section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">CURRENT TRUTH</span><h3>حالة النظام</h3></div></div><div className="status-list"><div><span>Self-hosted</span><b>{status?.self_hosted_configured?'متصل':'غير موصول'}</b></div><div><span>Runtime mode</span><b>{settings?.runtime_mode||'—'}</b></div><div><span>Pending approvals</span><b>{pendingTasks.length+pendingIntents.length}</b></div><div><span>In-flight actions</span><b>{attempts.filter(a=>a.phase==='IN_FLIGHT').length}</b></div></div></div><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">WEAKEST SKILLS</span><h3>أضعف المجالات</h3></div></div><div className="skill-stack">{skills.slice(0,6).map(s=><div className="skill-line" key={s.domain}><div><span>{domainNames[s.domain]||s.domain}</span><b>{Number(s.score||0).toFixed(0)}</b></div><div><i style={{width:`${Math.max(2,Number(s.score)||0)}%`}}/></div></div>)}</div></div></section></>}

      {tab==='runtime'&&<section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">RUNTIME</span><h3>المحرك والسياسة</h3><p>الإنفاق المدفوع مقفول في هذه المرحلة.</p></div></div>{settings&&<div className="form-grid"><label>وضع التشغيل<select value={settings.runtime_mode||'openrouter_primary'} onChange={e=>setSettings({...settings,runtime_mode:e.target.value})}><option value="openrouter_primary">OpenRouter Free أولًا</option><option value="openrouter_only">OpenRouter Free فقط</option><option value="self_hosted_primary">AQLEVON Self-hosted أولًا</option><option value="self_hosted_only">AQLEVON Self-hosted فقط</option></select></label><label>نموذج OpenRouter المجاني<input value={settings.openrouter_model||'openrouter/free'} onChange={e=>setSettings({...settings,openrouter_model:e.target.value})}/></label><label>Temperature<input type="number" min="0" max="2" step="0.1" value={settings.temperature??0.6} onChange={e=>setSettings({...settings,temperature:Number(e.target.value)})}/></label><label>سياق المحادثة<input type="number" min="4" max="64" value={settings.max_history||16} onChange={e=>setSettings({...settings,max_history:Number(e.target.value)})}/></label><label className="switch-row"><input type="checkbox" checked={!!settings.verification_enabled} onChange={e=>setSettings({...settings,verification_enabled:e.target.checked})}/><span><b>Formal Verification</b></span></label><label className="switch-row"><input type="checkbox" checked={!!settings.deep_reasoning_enabled} onChange={e=>setSettings({...settings,deep_reasoning_enabled:e.target.checked})}/><span><b>Deep Reasoning</b></span></label></div>}<div className="status-list"><div><span>Paid external</span><b>مغلق</b></div><div><span>Daily paid budget</span><b>$0</b></div><div><span>Self-hosted</span><b>{status?.self_hosted_configured?'متصل':'غير موصول بعد'}</b></div></div><button className="primary-btn fit" onClick={saveRuntime} disabled={busy}>حفظ الإعدادات</button></div><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">OPERATIONS</span><h3>Action execution truth</h3></div></div><div className="status-list"><div><span>Tasks</span><b>{tasks.length}</b></div><div><span>Action intents</span><b>{intents.length}</b></div><div><span>Attempts</span><b>{attempts.length}</b></div><div><span>Receipts</span><b>{receipts.length}</b></div></div></div></section>}

      {tab==='evaluation'&&<><section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">EVALUATION</span><h3>القياس المجاني</h3><p>يشغّل Benchmark واحدًا فقط مع zero-cost gate.</p></div></div><div className="status-list"><div><span>OpenRouter Free</span><b>{status?.openrouter_configured?'جاهز':'غير جاهز'}</b></div><div><span>Self-hosted AQLEVON</span><b>{status?.self_hosted_configured?'جاهز':'بانتظار GPU'}</b></div><div><span>Training candidates</span><b>{candidates.length}</b></div><div><span>Approved</span><b>{approved.length}</b></div></div><button className="primary-btn fit" onClick={runBenchmark} disabled={busy}>تشغيل Benchmark واحد</button></div><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">VERIFICATION</span><h3>الحقيقة قبل الترقية</h3></div></div><div className="status-list"><div><span>Verified traces</span><b>{verified}</b></div><div><span>Learning eligible</span><b>{eligible.length}</b></div><div><span>Evidence receipts</span><b>{receipts.length}</b></div><div><span>Unresolved attempts</span><b>{attempts.filter(a=>a.outcome==='UNKNOWN').length}</b></div></div></div></section></>}

      {tab==='learning'&&<><section className="admin-panel wide"><div className="panel-head"><div><span className="eyebrow">SECURE LEARNING GATE</span><h3>Traces المؤهلة للتعلم</h3><p>VERIFIED وحده لا يغيّر training set. الترقية تحتاج قرار المالك من هنا.</p></div></div><div className="table-list">{eligible.length?eligible.slice(0,40).map(x=>{const promoted=promotedIds.has(String(x.id));return <div className="table-row" key={x.id}><div><b>{domainNames[traceDomain(x)]||traceDomain(x)} · {x.difficulty||'—'}</b><span>{x.provider||'—'} · {x.model||'—'} · {x.model_calls||1} calls</span></div><span>{resultOf(x.verification)}</span><span>{x.latency_ms?`${x.latency_ms}ms`:'—'}</span><button className="primary-btn fit" disabled={busy||promoted} onClick={()=>promoteTrace(x.id)}>{promoted?'تمت الترقية':'ترقية للتعلم'}</button></div>}):<div className="empty-panel">لا توجد Traces VERIFIED مؤهلة حاليًا.</div>}</div></section><section className="admin-panel wide"><div className="panel-head"><div><span className="eyebrow">TRAINING REVIEW</span><h3>مراجعة Training Candidates</h3><p>لا يصبح المثال معتمدًا إلا بعد قرار المالك.</p></div></div><div className="table-list">{candidates.length?candidates.slice(0,50).map(x=><div className="table-row" key={x.id}><div><b>{String(x.user_input||'').slice(0,90)||'Training example'}</b><span>{(x.tags||[]).join(' · ')}</span></div><span>{x.quality_status}</span><div style={{display:'flex',gap:8}}><button className="primary-btn fit" disabled={busy} onClick={()=>reviewExample(x.id,'approved')}>اعتماد</button><button className="ghost-fit" disabled={busy} onClick={()=>reviewExample(x.id,'rejected')}>رفض</button></div></div>):<div className="empty-panel">لا توجد Candidates تنتظر المراجعة.</div>}</div></section></>}
    </main>
  </div>;
}