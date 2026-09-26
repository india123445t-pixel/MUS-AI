'use client';

import {useEffect,useMemo,useState} from 'react';
import {createClient} from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'https://yaqjhcfitxhtzpaswuif.supabase.co';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'sb_publishable_1uRtACKcyT2ZQH9ixdKQ-Q_ARbY6xET';

const domainNames={reasoning:'الاستدلال',math:'الرياضيات',science:'العلوم',coding:'البرمجة',language:'اللغة',research:'البحث',planning:'التخطيط',knowledge:'المعرفة',general:'عام',software:'البرمجة',data:'البيانات',communication:'التواصل',operations:'العمليات'};
const safeModes=['self_hosted_only'];
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
function isVerified(log){return resultOf(log?.verification)==='VERIFIED'}
function learningEligible(log){return isVerified(log)&&log?.learning_eligible===true}
function traceDomain(log){return log?.task_contract?.primary_domain||log?.task_contract?.domain||'general'}
function when(v){if(!v)return '—';try{return new Date(v).toLocaleString('ar-MA')}catch{return '—'}}
function short(v,n=12){const s=String(v||'');return s.length>n?`${s.slice(0,n)}…`:s||'—'}
function phaseLabel(v){return phases[v]||v||'—'}
function outcomeLabel(v){return outcomes[v]||v||'—'}
function executorLabel(v){return ({LIVE:'مباشر',IDLE:'خامل','NOT CONNECTED':'غير متصل',NOT_CONNECTED:'غير متصل',CONNECTED:'متصل'})[v]||v||'—'}
function sourceStatusLabel(v){return ({CONNECTED:'متصل',PARTIAL:'جزئي','ADAPTER REQUIRED':'يحتاج موصل تنفيذ'})[v]||v||'—'}
function verificationLabel(v){const r=resultOf(v);return ({VERIFIED:'موثّق',UNVERIFIED:'غير موثّق'})[r]||r||'غير موثّق'}
function actorLabel(v){return ({OWNER:'المالك',TASK:'مهمة',SYSTEM:'النظام',ADVISORY:'استشاري'})[v]||v||'—'}
function profileLabel(v){return ({guardian:'الحارس',engineer:'المهندس',model_lab:'مختبر النموذج',research:'البحث',authorized_security:'الأمن المصرّح'})[v]||v||'—'}
function qualityLabel(v){return ({candidate:'مرشح',approved:'معتمد',rejected:'مرفوض'})[v]||v||'—'}
function eventLabel(v){return ({OWNER_CORE_MISSION_PREPARED:'تم تحضير المهمة',OWNER_APPROVED_MISSION:'وافق المالك على المهمة',OWNER_CANCELLED_MISSION:'ألغى المالك المهمة',OWNER_STOP_REQUESTED:'طلب المالك الإيقاف'})[v]||v||'—'}
function responseTypeLabel(v){return ({APPROVAL_REQUEST:'طلب موافقة'})[v]||v||'—'}
function percentile(values,p){const xs=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!xs.length)return 0;const i=Math.min(xs.length-1,Math.max(0,Math.ceil((p/100)*xs.length)-1));return Math.round(xs[i])}

export default function AdminPage(){
  const sb=useMemo(()=>URL&&KEY?createClient(URL,KEY):null,[]);
  const [ready,setReady]=useState(false),[session,setSession]=useState(null),[authorized,setAuthorized]=useState(false);
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[authMsg,setAuthMsg]=useState('');
  const [recovery,setRecovery]=useState(false),[newPassword,setNewPassword]=useState('');
  const [status,setStatus]=useState(null),[settings,setSettings]=useState(null),[logs,setLogs]=useState([]),[examples,setExamples]=useState([]),[bench,setBench]=useState([]),[skills,setSkills]=useState([]);
  const [tasks,setTasks]=useState([]),[intents,setIntents]=useState([]),[attempts,setAttempts]=useState([]),[receipts,setReceipts]=useState([]),[audit,setAudit]=useState([]),[responses,setResponses]=useState([]);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[tab,setTab]=useState('owner');
  const [ownerBusy,setOwnerBusy]=useState(false),[ownerInput,setOwnerInput]=useState(''),[ownerProfile,setOwnerProfile]=useState('guardian'),[ownerMode,setOwnerMode]=useState('mission');
  const [ownerMessages,setOwnerMessages]=useState([{role:'assistant',text:'أنا نواة مالك AQLEVON. أعمل داخل لوحة المالك الخاصة. أستطيع تحليل المشروع وتحضير مهمة قابلة للموافقة، ولا أدّعي تنفيذ أي إجراء خارجي من دون تصريح وإيصال فعلي.'}]);
  const [selectedTask,setSelectedTask]=useState(null);
  const [selectedAttempt,setSelectedAttempt]=useState(null);
  const [globalQuery,setGlobalQuery]=useState('');
  const [traceFilter,setTraceFilter]=useState('ALL');

  useEffect(()=>{
    if(!sb){setReady(true);return}
    sb.auth.getSession().then(({data})=>{setSession(data.session||null);setReady(true)});
    const {data}=sb.auth.onAuthStateChange((event,s)=>{setSession(s);if(event==='PASSWORD_RECOVERY')setRecovery(true)});
    return()=>data.subscription.unsubscribe();
  },[sb]);

  useEffect(()=>{if(session)loadAll();else setAuthorized(false)},[session]);

  async function login(e){e.preventDefault();setAuthMsg('');const r=await sb.auth.signInWithPassword({email,password});if(r.error)setAuthMsg('بيانات الدخول غير صحيحة. استخدم «نسيت كلمة المرور؟» إذا لزم.')}
  async function requestPasswordReset(){
    const target=email.trim();if(!target){setAuthMsg('اكتب بريد المالك أولًا.');return}
    setAuthMsg('');
    const {error}=await sb.auth.resetPasswordForEmail(target,{redirectTo:window.location.origin+'/admin'});
    setAuthMsg(error?(error.message||'تعذر إرسال رابط الاستعادة.'):'تم إرسال رابط استعادة كلمة المرور إلى البريد. افتحه ثم عُد إلى هذه الصفحة.');
  }
  async function updateRecoveredPassword(e){
    e?.preventDefault?.();
    if(newPassword.length<10){setAuthMsg('اجعل كلمة المرور الجديدة 10 أحرف على الأقل.');return}
    setAuthMsg('');
    const {error}=await sb.auth.updateUser({password:newPassword});
    if(error){setAuthMsg(error.message||'تعذر تحديث كلمة المرور.');return}
    setNewPassword('');setRecovery(false);setAuthMsg('تم تغيير كلمة المرور بنجاح.');
  }
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
      const mode=safeModes.includes(settings.runtime_mode)?settings.runtime_mode:'self_hosted_only';
      const patch={runtime_mode:mode,temperature:Math.max(0,Math.min(2,Number(settings.temperature??0.6))),max_history:Math.max(4,Math.min(64,Number(settings.max_history||16))),public_chat_enabled:!!settings.public_chat_enabled,public_training_enabled:!!settings.public_training_enabled,save_training_candidates:!!settings.save_training_candidates,intelligence_router_enabled:!!settings.intelligence_router_enabled,verification_enabled:!!settings.verification_enabled,deep_reasoning_enabled:!!settings.deep_reasoning_enabled,max_model_calls_per_request:Math.max(1,Math.min(4,Number(settings.max_model_calls_per_request||3))),allow_paid_external:false,daily_budget_usd:0};
      const {error}=await sb.from('control_settings').update(patch).eq('owner_id',settings.owner_id);if(error)throw error;
      setNotice('تم حفظ إعدادات AQLEVON مع إبقاء الإنفاق المدفوع مقفلاً عند صفر.');await loadAll();
    }catch(e){setNotice(e?.message||'تعذر حفظ الإعدادات.')}finally{setBusy(false)}
  }

  async function runBenchmark(){if(!session)return;setBusy(true);setNotice('');try{const r=await fetch('/api/benchmark/run',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:'{}'});const d=await r.json();if(!r.ok)throw new Error(d.message||'فشل الاختبار.');setNotice(`Benchmark ${domainNames[d.domain]||d.domain}: ${d.score}/100`);await loadAll()}catch(e){setNotice(e?.message||'فشل التقييم.')}finally{setBusy(false)}}
  async function promoteTrace(id){setBusy(true);setNotice('');try{const {data,error}=await sb.rpc('promote_verified_chat_to_training',{p_chat_log_id:id});if(error)throw error;setNotice(`تمت ترقية الـtrace إلى Training Candidate: ${data}`);await loadAll()}catch(e){setNotice(e?.message||'تعذر ترقية التتبّع.')}finally{setBusy(false)}}
  async function reviewExample(id,quality_status){setBusy(true);setNotice('');try{const {error}=await sb.from('training_examples').update({quality_status}).eq('id',id);if(error)throw error;setNotice(quality_status==='approved'?'تم اعتماد المثال.':'تم رفض المثال.');await loadAll()}catch(e){setNotice(e?.message||'تعذر تحديث المثال.')}finally{setBusy(false)}}

  async function ownerSend(e){
    e?.preventDefault?.();
    const input=ownerInput.trim();if(!input||!session||ownerBusy)return;
    const prior=ownerMessages.slice(-12).map(m=>({role:m.role,content:m.text}));
    setOwnerMessages(v=>[...v,{role:'user',text:input}]);setOwnerInput('');setOwnerBusy(true);setNotice('');
    try{
      const r=await fetch('/api/admin/owner-core/chat',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:JSON.stringify({input,history:prior,profile:ownerProfile,mode:ownerMode})});
      const d=await r.json();if(!r.ok)throw new Error(d.message||'تعذر تشغيل نواة المالك.');
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
  if(recovery&&session)return <div className="admin-login-shell"><form className="admin-login-card" onSubmit={updateRecoveredPassword}><img src="/admin-icon.svg" alt="AQLEVON AI"/><span className="eyebrow">استعادة حساب المالك</span><h1>كلمة مرور جديدة</h1><p>اكتب كلمة مرور جديدة لحساب المالك ثم احفظها.</p><label>كلمة المرور الجديدة<input type="password" minLength="10" value={newPassword} onChange={e=>setNewPassword(e.target.value)} required/></label><button className="primary-btn" type="submit">حفظ كلمة المرور</button>{authMsg&&<div className="auth-msg">{authMsg}</div>}</form></div>;
  if(!session)return <div className="admin-login-shell"><form className="admin-login-card" onSubmit={login}><img src="/admin-icon.svg" alt="AQLEVON AI"/><span className="eyebrow">مركز التحكم الخاص</span><h1>AQLEVON AI</h1><div className="admin-version-badge">نواة المالك V3 · منصة التتبّع</div><p>لوحة الإدارة الخاصة بالمشروع.</p><label>البريد الإلكتروني<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>كلمة المرور<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label><button className="primary-btn" type="submit">دخول</button><button className="ghost-fit" type="button" onClick={requestPasswordReset}>نسيت كلمة المرور؟</button>{authMsg&&<div className="auth-msg">{authMsg}</div>}</form></div>;
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
  const closedTasks=tasks.filter(t=>t.phase==='CLOSED');
  const successfulTasks=closedTasks.filter(t=>t.outcome==='SUCCESS');
  const successRate=closedTasks.length?Math.round(successfulTasks.length/closedTasks.length*100):0;
  const avgLatency=logs.length?Math.round(logs.reduce((sum,x)=>sum+Number(x.latency_ms||0),0)/logs.length):0;
  const evidenceCoverage=attempts.length?Math.min(100,Math.round(receipts.length/attempts.length*100)):0;
  const incidentCount=attempts.filter(a=>['FAILED','UNKNOWN'].includes(a.outcome)).length;
  const latestModel=logs.find(x=>x.model)?.model||'AQLEVON';
  const executorState='NOT_CONNECTED';
  const latencyValues=logs.map(x=>Number(x.latency_ms||0)).filter(x=>x>0);
  const p50Latency=percentile(latencyValues,50),p95Latency=percentile(latencyValues,95),p99Latency=percentile(latencyValues,99);
  const terminalAttempts=attempts.filter(a=>['SUCCESS','PARTIAL','FAILED','CANCELLED'].includes(a.outcome));
  const toolSuccessRate=terminalAttempts.length?Math.round(terminalAttempts.filter(a=>a.outcome==='SUCCESS').length/terminalAttempts.length*100):0;
  const q=globalQuery.trim().toLowerCase();
  const filteredTasks=tasks.filter(t=>!q||String(t.title||'').toLowerCase().includes(q)||String(t.id||'').toLowerCase().includes(q)||String(t.scope?.profile||'').toLowerCase().includes(q));
  const filteredAttempts=attempts.filter(a=>{
    const matchFilter=traceFilter==='ALL'||a.phase===traceFilter||a.outcome===traceFilter;
    const matchQuery=!q||[a.id,a.task_id,a.provider_operation_id,a.permit_id,a.phase,a.outcome].some(v=>String(v||'').toLowerCase().includes(q));
    return matchFilter&&matchQuery;
  });
  const activeAttempt=attempts.find(a=>a.id===selectedAttempt)||filteredAttempts[0]||null;
  const activeAttemptTask=activeAttempt?tasks.find(t=>t.id===activeAttempt.task_id):null;
  const activeAttemptIntent=activeAttempt?intents.find(i=>i.id===activeAttempt.action_intent_id):null;
  const activeAttemptReceipt=activeAttempt?receipts.find(r=>r.action_attempt_id===activeAttempt.id):null;
  const activeAttemptAudit=activeAttempt?audit.filter(e=>e.task_id===activeAttempt.task_id).slice(0,16):[];
  const securityTasks=tasks.filter(t=>t.scope?.profile==='authorized_security');
  const sourceHealth=[
    ['طبقة التحكم','CONNECTED','المهام · نيات التنفيذ · المحاولات · الإيصالات'],
    ['تدقيق المشروع','CONNECTED',`${audit.length} أحداث حديثة محملة`],
    ['مخزن التقييم','CONNECTED',`${bench.length} تقييمات · ${verified} تتبّعات موثقة`],
    ['بوابة التعلّم','CONNECTED',`${candidates.length} مرشحات · ${approved.length} معتمدة`],
    ['Git / النشر / المتصفح','ADAPTER REQUIRED','جسر التنفيذ غير متصل'],
    ['الأوزان / السجل','PARTIAL','قياس النموذج ظاهر؛ سجل النسب قيد الربط']
  ];

  return <div className="owner-admin-shell" dir="rtl">
    <aside className="owner-admin-sidebar">
      <div className="owner-brand"><img src="/admin-icon.svg" alt="AQLEVON"/><div><strong>AQLEVON</strong><span>تحكم المالك</span></div></div>
      <nav>
        <span className="owner-nav-kicker">التشغيل</span>
        {nav.filter(([id])=>['owner','missions','traces','incidents','overview'].includes(id)).map(([id,label])=><button key={id} className={tab===id?'active':''} onClick={()=>setTab(id)}><span>{label}</span>{id==='owner'&&pendingTasks.length>0?<b>{pendingTasks.length}</b>:null}</button>)}
        <span className="owner-nav-kicker">الذكاء</span>
        {nav.filter(([id])=>['brain','model_lab','evaluation','learning'].includes(id)).map(([id,label])=><button key={id} className={tab===id?'active':''} onClick={()=>setTab(id)}><span>{label}</span></button>)}
        <span className="owner-nav-kicker">النظام</span>
        {nav.filter(([id])=>['infrastructure','security','runtime','access'].includes(id)).map(([id,label])=><button key={id} className={tab===id?'active':''} onClick={()=>setTab(id)}><span>{label}</span></button>)}
      </nav>
      <div className="owner-side-status"><span>صلاحية المالك</span><strong>نشط</strong><small>{session.user?.email||'system_owner'}</small></div>
      <div className="owner-side-actions"><a href="/admin/child-lab">مختبر الطفل ↗</a><a href="/" target="_blank">فتح التطبيق العام ↗</a><button onClick={()=>sb.auth.signOut()}>تسجيل الخروج</button></div>
    </aside>

    <main className="owner-admin-main">
      <header className="owner-admin-header v3-header">
        <div className="v3-title"><span className="eyebrow">AQLEVON · نواة المالك V3 · منصة التتبّع</span><h1>{nav.find(x=>x[0]===tab)?.[1]}</h1></div>
        <div className="v3-global-search"><span>⌕</span><input value={globalQuery} onChange={e=>setGlobalQuery(e.target.value)} placeholder="ابحث في المهام والتتبّعات والمعرّفات والمزوّدين…"/></div>
        <div className="header-actions">
          <span className="v3-env-pill">معاينة</span>
          <span className={`health-pill ${status?.self_hosted_configured?'ok':'warn'}`}><i/>{status?.self_hosted_configured?'AQLEVON متصل':'AQLEVON غير متصل'}</span>
          <button className="refresh-btn" onClick={loadAll} disabled={busy}>{busy?'…':'↻'}</button>
        </div>
      </header>
      {notice&&<div className="admin-notice">{notice}</div>}

      {tab==='owner'&&<>
        <section className="v3-command-head">
          <div><span className="eyebrow">نواة مالك AQLEVON V3 · منصة القيادة</span><h2>قيادة AQLEVON</h2><p>أرسل الأمر، راجع المهمة، وافق، ثم راقب التنفيذ والأدلة دون مغادرة نفس مساحة العمل.</p></div>
          <div className="v3-command-status">
            <span><i className={executorState==='LIVE'?'live':''}/>{executorLabel(executorState)}</span>
            <span>{pendingTasks.length+pendingIntents.length} approvals</span>
            <span>{incidentCount} incidents</span>
            <span>{evidenceCoverage}% evidence</span>
          </div>
        </section>

        <section className="command-workbench">
          <div className="command-chat-pane">
            <div className="command-pane-bar">
              <div><b>جلسة التشغيل</b><span>{session.user?.email||'system_owner'}</span></div>
              <div className="owner-inline-controls">
                <select value={ownerProfile} onChange={e=>setOwnerProfile(e.target.value)}>{profiles.map(x=><option key={x[0]} value={x[0]}>{x[1]}</option>)}</select>
                <select value={ownerMode} onChange={e=>setOwnerMode(e.target.value)}><option value="chat">تحليل</option><option value="mission">تحضير مهمة</option></select>
              </div>
            </div>
            <div className="command-context-bar"><span>النمط</span><b>{profiles.find(x=>x[0]===ownerProfile)?.[1]}</b><small>{profiles.find(x=>x[0]===ownerProfile)?.[2]}</small></div>
            <div className="command-chat-stream">
              {ownerMessages.map((m,i)=><div key={i} className={`command-message ${m.role} ${m.error?'error':''}`}><div className="command-message-meta"><span>{m.role==='user'?'المالك':'AQLEVON'}</span>{m.meta&&<small>{actorLabel(m.meta.execution_state||'ADVISORY')} · {short(m.meta.run_id,8)}</small>}</div><p>{m.text}</p></div>)}
              {ownerBusy&&<div className="command-message assistant"><div className="command-message-meta"><span>AQLEVON</span></div><p>يتم تحضير الرد…</p></div>}
            </div>
            <form className="command-composer" onSubmit={ownerSend}>
              <textarea value={ownerInput} onChange={e=>setOwnerInput(e.target.value)} placeholder="أعط AQLEVON أمرًا، اطلب تحليل المشروع، أو حضّر مهمة للتنفيذ…" rows="3"/>
              <div><span>{ownerMode==='mission'?'تتطلب المهمة موافقة صريحة من المالك قبل أي تنفيذ خارجي.':'وضع استشاري · لا يتم إنشاء أو تعديل مهمة.'}</span><button className="primary-btn" disabled={ownerBusy||!ownerInput.trim()}>{ownerMode==='mission'?'تحضير المهمة':'إرسال'}</button></div>
            </form>
          </div>

          <aside className="command-control-rail">
            <div className="command-rail-head"><div><span className="eyebrow">التحكم بالمهام</span><h3>{activeTask?.title||'لم يتم اختيار مهمة'}</h3></div><span className={`v3-state-pill ${String(activeTask?.phase||'idle').toLowerCase()}`}>{activeTask?.phase?phaseLabel(activeTask.phase):'خامل'}</span></div>
            <div className="command-queue">
              <div className="command-queue-title"><b>قائمة الانتظار</b><span>{tasks.length}</span></div>
              {tasks.length?tasks.slice(0,9).map(t=><button key={t.id} className={activeTask?.id===t.id?'active':''} onClick={()=>setSelectedTask(t.id)}><div><b>{t.title||'مهمة AQLEVON'}</b><small>{short(t.id,12)} · {when(t.updated_at||t.created_at)}</small></div><span>{phaseLabel(t.phase)}</span></button>):<div className="empty-panel">لا توجد مهام بعد.</div>}
            </div>
            {activeTask&&<div className="command-mission-detail">
              <div className="v3-kv"><span>النتيجة</span><b>{outcomeLabel(activeTask.outcome)}</b></div>
              <div className="v3-kv"><span>النمط</span><b>{profileLabel(activeTask.scope?.profile)}</b></div>
              <div className="v3-kv"><span>الاستقلالية</span><b>{activeTask.scope?.autonomy||'approval_required'}</b></div>
              <div className="v3-kv"><span>المنفّذ</span><b>{executorLabel(executorState)}</b></div>
              {activeTask.phase==='OPEN'&&<div className="v3-action-row"><button className="primary-btn" onClick={()=>taskAction(activeTask.id,'approve')} disabled={busy}>موافقة</button><button className="ghost-fit" onClick={()=>taskAction(activeTask.id,'cancel')} disabled={busy}>إلغاء</button></div>}
              <button className="owner-stop-btn" disabled={!hasInFlight} onClick={()=>taskAction(activeTask.id,'stop')}>إيقاف الآن</button>
            </div>}
          </aside>
        </section>

        <section className="command-lower-grid">
          <div className="command-live-pane">
            <div className="trace-pane-title"><b>التنفيذ المباشر</b><span>{hasInFlight?'مباشر':'لا يوجد منفّذ نشط'}</span></div>
            <div className="command-live-rows">
              {activeAttempts.length?activeAttempts.slice(0,12).map(a=><button key={a.id} onClick={()=>{setSelectedAttempt(a.id);setTab('traces')}}><span className={a.phase==='IN_FLIGHT'?'live-dot-cell':''}>{phaseLabel(a.phase)}</span><code>attempt #{a.attempt_no}</code><span>{short(a.provider_operation_id,18)}</span><b>{outcomeLabel(a.outcome)}</b></button>):<div className="command-empty-console">لا يوجد منفّذ خارجي متصل. ستظهر أنشطة الأدوات هنا فقط عند وجود محاولات تنفيذ حقيقية.</div>}
            </div>
          </div>
          <div className="command-audit-pane">
            <div className="trace-pane-title"><b>الأدلة وسجل التدقيق</b><button onClick={()=>setTab('traces')}>فتح التتبّع ↗</button></div>
            <div className="command-audit-list">{activeAudit.length?activeAudit.slice(0,10).map(e=><div key={e.id}><i/><div><b>{eventLabel(e.event_type)}</b><small>{actorLabel(e.subject_type||'TASK')} · {when(e.created_at)}</small></div></div>):<div className="empty-panel">لا توجد أحداث تدقيق لهذه المهمة.</div>}</div>
          </div>
        </section>

        <section className="command-system-strip">
          <button onClick={()=>setTab('brain')}><span>ذاكرة المشروع</span><b>طبقة التحكم</b><small>{audit.length} أحداث تدقيق</small></button>
          <button onClick={()=>setTab('model_lab')}><span>النموذج</span><b>{short(latestModel,22)}</b><small>{avgBench==='—'?'لا يوجد تقييم':avgBench+'/100 تقييم'}</small></button>
          <button onClick={()=>setTab('traces')}><span>المراقبة</span><b>P95 {p95Latency?p95Latency+'ms':'—'}</b><small>{toolSuccessRate}% tool success</small></button>
          <button onClick={()=>setTab('infrastructure')}><span>المنفّذون</span><b>{executorLabel(executorState)}</b><small>موصلات Git والمتصفح والنشر</small></button>
          <button onClick={()=>setTab('security')}><span>الأمن</span><b>ضمن نطاق مصرح فقط</b><small>{securityTasks.length} مهام مصرّح بها</small></button>
        </section>
      </>}

      {tab==='missions'&&<>
        <section className="v3-section-head"><div><span className="eyebrow">سجل المهام</span><h2>مهام تحت سيطرة المالك</h2><p>المهام الحقيقية وحالتها وحدودها وقرارات المالك في سجل واحد.</p></div><div className="v3-head-stats"><span>{filteredTasks.length} visible</span><span>{pendingTasks.length} approval</span><span>{runningTasks.length} active</span></div></section>
        <section className="mission-workbench">
          <div className="mission-table-pane">
            <div className="v3-table-head mission-grid"><span>المهمة</span><span>المرحلة</span><span>النتيجة</span><span>النمط</span><span>المنفّذ</span><span>آخر تحديث</span></div>
            <div className="v3-scroll-list">{filteredTasks.length?filteredTasks.map(t=><button className={`v3-table-row mission-grid ${activeTask?.id===t.id?'selected':''}`} key={t.id} onClick={()=>setSelectedTask(t.id)}><span className="mission-title"><b>{t.title||'مهمة AQLEVON'}</b><small>{short(t.id,14)}</small></span><span>{phaseLabel(t.phase)}</span><span className={`tone-${String(t.outcome||'NONE').toLowerCase()}`}>{outcomeLabel(t.outcome)}</span><span>{profileLabel(t.scope?.profile)}</span><span>{executorState}</span><span>{when(t.updated_at||t.created_at)}</span></button>):<div className="empty-panel">لا توجد مهام تطابق البحث الحالي.</div>}</div>
          </div>
          <aside className="v3-inspector">
            <div className="v3-inspector-head"><span className="eyebrow">تفاصيل المهمة</span><h3>{activeTask?.title||'اختر مهمة'}</h3><small>{activeTask?.id||'—'}</small></div>
            {activeTask&&<>
              <div className="v3-kv"><span>المرحلة</span><b>{phaseLabel(activeTask.phase)}</b></div>
              <div className="v3-kv"><span>النتيجة</span><b>{outcomeLabel(activeTask.outcome)}</b></div>
              <div className="v3-kv"><span>النمط</span><b>{profileLabel(activeTask.scope?.profile)}</b></div>
              <div className="v3-kv"><span>الاستقلالية</span><b>{activeTask.scope?.autonomy||'approval_required'}</b></div>
              <div className="v3-kv"><span>المنفّذ</span><b>{executorLabel(executorState)}</b></div>
              <div className="v3-divider"/>
              {activeTask.phase==='OPEN'&&<div className="v3-action-row"><button className="primary-btn" onClick={()=>taskAction(activeTask.id,'approve')} disabled={busy}>موافقة</button><button className="ghost-fit" onClick={()=>taskAction(activeTask.id,'cancel')} disabled={busy}>إلغاء</button></div>}
              <button className="owner-stop-btn" disabled={!hasInFlight} onClick={()=>taskAction(activeTask.id,'stop')}>إيقاف الآن</button>
              <div className="v3-subhead">الخط الزمني للأدلة</div>
              <div className="v3-event-list">{activeAudit.length?activeAudit.map(e=><div key={e.id}><i/><div><b>{eventLabel(e.event_type)}</b><small>{when(e.created_at)}</small></div></div>):<span className="empty-inline">لا توجد أحداث تدقيق.</span>}</div>
            </>}
          </aside>
        </section>
      </>}

      {tab==='traces'&&<>
        <section className="trace-toolbar">
          <div><span className="eyebrow">مستكشف التتبّع</span><h2>مراقبة التنفيذ</h2></div>
          <div className="trace-metrics"><span>P50 <b>{p50Latency?p50Latency+'ms':'—'}</b></span><span>P95 <b>{p95Latency?p95Latency+'ms':'—'}</b></span><span>P99 <b>{p99Latency?p99Latency+'ms':'—'}</b></span><span>نجاح الأدوات <b>{toolSuccessRate}%</b></span><span>المحاولات <b>{attempts.length}</b></span><span>الإيصالات <b>{receipts.length}</b></span></div>
          <select value={traceFilter} onChange={e=>setTraceFilter(e.target.value)}><option value="ALL">كل التتبّعات</option><option value="IN_FLIGHT">قيد التنفيذ</option><option value="CLOSED">مغلقة</option><option value="SUCCESS">نجاح</option><option value="FAILED">فشل</option><option value="UNKNOWN">غير محسوم</option></select>
        </section>
        <section className="trace-workbench">
          <div className="trace-list-pane">
            <div className="trace-pane-title"><b>التشغيلات</b><span>{filteredAttempts.length}</span></div>
            <div className="trace-run-list">{filteredAttempts.length?filteredAttempts.slice(0,80).map(a=><button key={a.id} className={activeAttempt?.id===a.id?'selected':''} onClick={()=>{setSelectedAttempt(a.id);setSelectedTask(a.task_id)}}><div><i className={a.phase==='IN_FLIGHT'?'live':''}/><b>{activeAttemptTask?.id===a.task_id?(activeAttemptTask?.title||'Mission'):(tasks.find(t=>t.id===a.task_id)?.title||'Mission')}</b></div><span>{phaseLabel(a.phase)} · {outcomeLabel(a.outcome)}</span><small>#{a.attempt_no} · {when(a.started_at||a.created_at)}</small></button>):<div className="empty-panel">لا توجد تتبّعات تنفيذ مسجلة بعد.</div>}</div>
          </div>
          <div className="trace-tree-pane">
            <div className="trace-pane-title"><b>تتبّع طبقة التحكم</b><span>{activeAttempt?short(activeAttempt.id,10):'—'}</span></div>
            {activeAttempt?<div className="trace-tree">
              <div className="trace-node root"><i/><div><span>مهمة</span><b>{activeAttemptTask?.title||'مهمة AQLEVON'}</b><small>{activeAttempt.task_id}</small></div></div>
              <div className="trace-node"><i/><div><span>نية تنفيذ</span><b>{activeAttemptIntent?.semantic_action||'نية تنفيذ'}</b><small>{activeAttemptIntent?.canonical_resource||'لا يوجد مورد معياري'}</small></div></div>
              <div className="trace-node active"><i/><div><span>محاولة</span><b>{phaseLabel(activeAttempt.phase)} · {outcomeLabel(activeAttempt.outcome)}</b><small>{activeAttempt.provider_operation_id||'لا يوجد معرّف لعملية المزوّد'}</small></div></div>
              <div className={`trace-node ${activeAttemptReceipt?'verified':'muted'}`}><i/><div><span>إيصال</span><b>{activeAttemptReceipt?.executor_reported_outcome||'لا يوجد إيصال بعد'}</b><small>{activeAttemptReceipt?.executor_identity||'الأدلة قيد الانتظار'}</small></div></div>
              {activeAttemptAudit.slice(0,5).map(e=><div className="trace-node audit" key={e.id}><i/><div><span>تدقيق</span><b>{eventLabel(e.event_type)}</b><small>{when(e.created_at)}</small></div></div>)}
            </div>:<div className="empty-panel">اختر تتبّعًا لعرض التفاصيل.</div>}
          </div>
          <aside className="trace-inspector">
            <div className="trace-pane-title"><b>التفاصيل</b><span>{activeAttempt?phaseLabel(activeAttempt.phase):'—'}</span></div>
            {activeAttempt&&<>
              <div className="v3-inspector-tabs"><span className="active">التفاصيل</span><span>الأدلة</span><span>التدقيق</span></div>
              <div className="v3-kv"><span>المحاولة</span><code>{activeAttempt.id}</code></div>
              <div className="v3-kv"><span>التصريح</span><code>{activeAttempt.permit_id||'—'}</code></div>
              <div className="v3-kv"><span>عملية المزوّد</span><code>{activeAttempt.provider_operation_id||'—'}</code></div>
              <div className="v3-kv"><span>بدأ</span><b>{when(activeAttempt.started_at||activeAttempt.created_at)}</b></div>
              <div className="v3-kv"><span>مغلقة</span><b>{when(activeAttempt.closed_at)}</b></div>
              <div className="v3-divider"/>
              <div className="v3-subhead">النية التنفيذية</div>
              <pre className="trace-json">{JSON.stringify({action:activeAttemptIntent?.semantic_action||null,resource:activeAttemptIntent?.canonical_resource||null,parameters:activeAttemptIntent?.canonical_parameters||null},null,2)}</pre>
              <div className="v3-subhead">الإيصال</div>
              <pre className="trace-json">{JSON.stringify(activeAttemptReceipt?{executor:activeAttemptReceipt.executor_identity,transport:activeAttemptReceipt.transport_status,outcome:activeAttemptReceipt.executor_reported_outcome,operation:activeAttemptReceipt.provider_operation_id}:{status:'NO_RECEIPT'},null,2)}</pre>
            </>}
          </aside>
        </section>
        <section className="model-trace-strip">
          <div className="trace-pane-title"><b>حركة النموذج</b><span>{logs.length} recent traces</span></div>
          <div className="model-trace-table">{logs.slice(0,18).map(x=><div key={x.id}><span>{domainNames[traceDomain(x)]||traceDomain(x)}</span><b>{short(x.model,20)}</b><span>{x.latency_ms?x.latency_ms+'ms':'—'}</span><span>{x.model_calls||1} استدعاءات</span><span className={isVerified(x)?'verified':''}>{verificationLabel(x.verification)}</span></div>)}</div>
        </section>
      </>}

      {tab==='incidents'&&<>
        <section className="v3-section-head"><div><span className="eyebrow">مركز الحوادث</span><h2>الإخفاقات والتنفيذ غير المحسوم</h2><p>كل فشل أو نتيجة غير محسومة تظهر هنا لتتحول من سجل مبعثر إلى مسار تحقيق واضح.</p></div><div className="v3-head-stats"><span>{incidentCount} إشارات مفتوحة</span><span>{attempts.filter(a=>a.outcome==='FAILED').length} فاشلة</span><span>{attempts.filter(a=>a.outcome==='UNKNOWN').length} غير محسومة</span></div></section>
        <section className="incident-console">
          <div className="incident-table">
            <div className="incident-head"><span>الخطورة</span><span>المهمة / المحاولة</span><span>الحالة</span><span>عملية المزوّد</span><span>الوقت</span></div>
            {attempts.filter(a=>['FAILED','UNKNOWN'].includes(a.outcome)).length?attempts.filter(a=>['FAILED','UNKNOWN'].includes(a.outcome)).map(a=><button key={a.id} onClick={()=>{setSelectedAttempt(a.id);setSelectedTask(a.task_id);setTab('traces')}}><span className={a.outcome==='FAILED'?'sev-high':'sev-warn'}>{a.outcome==='FAILED'?'مرتفع':'مراجعة'}</span><span><b>{tasks.find(t=>t.id===a.task_id)?.title||'مهمة AQLEVON'}</b><small>{short(a.id,14)}</small></span><span>{phaseLabel(a.phase)} · {outcomeLabel(a.outcome)}</span><code>{short(a.provider_operation_id,18)}</code><span>{when(a.started_at||a.created_at)}</span></button>):<div className="empty-panel">لا توجد محاولات تنفيذ فاشلة أو غير محسومة.</div>}
          </div>
          <aside className="incident-guidance"><span className="eyebrow">سياسة المعالجة</span><h3>الأدلة قبل الإغلاق</h3><p>لا نغلق الحادث لأن المنفّذ قال «نجاح». الإغلاق يعتمد على الإيصال والتحقق وسجل التدقيق.</p><div className="v3-kv"><span>تغطية الأدلة</span><b>{evidenceCoverage}%</b></div><div className="v3-kv"><span>نتائج غير محسومة</span><b>{attempts.filter(a=>a.outcome==='UNKNOWN').length}</b></div><div className="v3-kv"><span>طلبات الإيقاف</span><b>{audit.filter(e=>e.event_type==='OWNER_STOP_REQUESTED').length}</b></div></aside>
        </section>
      </>}

      {tab==='brain'&&<>
        <section className="brain-hero">
          <div><span className="eyebrow">ذاكرة المشروع</span><h2>خريطة الحقيقة التشغيلية</h2><p>مصادر الحقيقة التي تعتمد عليها نواة المالك الآن، وما هو موصول فعليًا وما زال يحتاج موصل تنفيذ.</p></div>
          <div className="brain-score"><span>المصادر المتصلة</span><strong>{sourceHealth.filter(x=>x[1]==='CONNECTED').length}/{sourceHealth.length}</strong></div>
        </section>
        <section className="brain-grid">
          {sourceHealth.map(([name,state,detail])=><div className="brain-source" key={name}><div><i className={state==='CONNECTED'?'ok':state==='PARTIAL'?'warn':''}/><span>{name}</span></div><b>{sourceStatusLabel(state)}</b><small>{detail}</small></div>)}
        </section>
        <section className="panel-grid">
          <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">القرارات الأخيرة</span><h3>ذاكرة التدقيق</h3></div></div><div className="owner-timeline">{audit.slice(0,18).map(e=><div key={e.id}><i/><div><b>{eventLabel(e.event_type)}</b><span>{actorLabel(e.subject_type||'SYSTEM')} · {when(e.created_at)}</span></div></div>)}</div></div>
          <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">مخرجات نواة المالك</span><h3>آخر الردود المحفوظة</h3></div></div><div className="brain-response-list">{responses.slice(0,12).map(r=><div key={r.id}><b>{responseTypeLabel(r.response_type)}</b><p>{String(r.body||'').slice(0,180)}</p><span>{when(r.emitted_at)}</span></div>)}</div></div>
        </section>
      </>}

      {tab==='model_lab'&&<>
        <section className="model-lab-hero">
          <div><span className="eyebrow">مختبر النموذج</span><h2>{short(latestModel,34)}</h2><p>قياس الجودة والمهارات والتتبّعات وحالة التعلّم قبل أي ادعاء بتحسن النموذج.</p></div>
          <div className="model-lab-kpis"><div><span>التقييم</span><b>{avgBench==='—'?'—':avgBench+'/100'}</b></div><div><span>متوسط المهارات</span><b>{avgSkill==='—'?'—':avgSkill+'/100'}</b></div><div><span>موثّق</span><b>{verified}</b></div><div><span>بيانات معتمدة</span><b>{approved.length}</b></div></div>
        </section>
        <section className="panel-grid">
          <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">خريطة القدرات</span><h3>حالة المهارات</h3></div></div><div className="skill-stack">{skills.slice(0,12).map(s=><div className="skill-line" key={s.domain}><div><span>{domainNames[s.domain]||s.domain}</span><b>{Number(s.score||0).toFixed(0)}</b></div><div><i style={{width:`${Math.max(2,Number(s.score)||0)}%`}}/></div></div>)}</div></div>
          <div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">سجل التقييم</span><h3>نتائج التقييم الأخيرة</h3></div></div><div className="eval-list">{bench.slice(0,16).map(b=><div key={b.id}><div><b>{b.model_label||'AQLEVON'}</b><span>{when(b.created_at)}</span></div><strong>{Number(b.score||0).toFixed(1)}</strong><small>{b.judge||'judge'}</small></div>)}</div></div>
        </section>
      </>}

      {tab==='access'&&<>
        <section className="access-hero"><div><span className="eyebrow">الهوية والصلاحيات</span><h2>حدود التنفيذ تحت سيطرة المالك</h2><p>هوية المالك، مزودات التشغيل، وحدود الصلاحيات المستخدمة في المهام.</p></div><span className="access-owner-badge">مالك النظام · نشط</span></section>
        <section className="access-grid">
          <div className="access-card connected"><span>هوية المالك</span><b>{session.user?.email||'system_owner'}</b><small>مصادقة Supabase + سجل مالك النظام</small></div>
          <div className="access-card connected"><span>طبقة تحكم Supabase</span><b>متصل</b><small>المصادقة · المهام · الإيصالات · التدقيق · التعلّم</small></div>
          <div className="access-card"><span>منفّذ Git / المستودع</span><b>غير متصل</b><small>يلزم موصل تنفيذ قبل أي تعديل تلقائي للكود</small></div>
          <div className="access-card"><span>منفّذ المتصفح / الطرفية</span><b>غير متصل</b><small>لا يتم الادعاء بأي تنفيذ خارجي غير موجود</small></div>
          <div className="access-card"><span>منفّذ النشر</span><b>غير متصل</b><small>النشر يتطلب مهمة وافق عليها المالك صراحة</small></div>
          <div className="access-card warning"><span>الحوسبة المدفوعة</span><b>مقفلة</b><small>ميزانية التشغيل المدفوع اليومية الحالية: 0 دولار</small></div>
          <div className="access-card warning"><span>الأمن المصرّح</span><b>ضمن نطاق مصرح فقط</b><small>يتطلب تحديد الهدف والنطاق صراحة داخل المهمة</small></div>
          <div className="access-card connected"><span>أدلة التدقيق</span><b>{audit.length} أحداث</b><small>{receipts.length} إيصالات تنفيذ محملة</small></div>
        </section>
      </>}

      {tab==='overview'&&<><section className="metric-grid"><Metric label="الحالة" value={status?.self_hosted_configured?'متصل':'يحتاج إعداد'} sub={settings?.runtime_mode||'—'}/><Metric label="Verified" value={logs.length?`${Math.round(verified/logs.length*100)}%`:'—'} sub={`${verified} من ${logs.length}`}/><Metric label="Benchmark" value={avgBench==='—'?'—':`${avgBench}/100`} sub={`${bench.length} نتائج`}/><Metric label="متوسط القدرات" value={avgSkill==='—'?'—':`${avgSkill}/100`} sub={`${skills.length} مجالات`}/><Metric label="Missions" value={tasks.length} sub={`${runningTasks.length} نشطة`}/><Metric label="Receipts" value={receipts.length} sub="أدلة تنفيذ مسجلة"/></section><section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">الحالة الفعلية</span><h3>حالة النظام</h3></div></div><div className="status-list"><div><span>ذاتي الاستضافة</span><b>{status?.self_hosted_configured?'متصل':'غير موصول'}</b></div><div><span>وضع التشغيل</span><b>{settings?.runtime_mode||'—'}</b></div><div><span>موافقات معلقة</span><b>{pendingTasks.length+pendingIntents.length}</b></div><div><span>إجراءات قيد التنفيذ</span><b>{attempts.filter(a=>a.phase==='IN_FLIGHT').length}</b></div></div></div><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">أضعف المهارات</span><h3>أضعف المجالات</h3></div></div><div className="skill-stack">{skills.slice(0,6).map(s=><div className="skill-line" key={s.domain}><div><span>{domainNames[s.domain]||s.domain}</span><b>{Number(s.score||0).toFixed(0)}</b></div><div><i style={{width:`${Math.max(2,Number(s.score)||0)}%`}}/></div></div>)}</div></div></section></>}

      {tab==='infrastructure'&&<>
        <section className="v3-section-head"><div><span className="eyebrow">البنية التحتية</span><h2>بيئة التشغيل والتنفيذ</h2><p>الحالة التي نعرفها فعليًا من النظام، مع فصل واضح بين المتصل وغير الموصول.</p></div></section>
        <section className="infra-matrix">
          <div className="infra-row"><div><i className="ok"/><b>طبقة تحكم Supabase</b></div><span>متصل</span><small>المصادقة · المهام · الإيصالات · التدقيق · التعلّم</small></div>
          <div className="infra-row"><div><i className={status?.self_hosted_configured?'ok':'warn'}/><b>AQLEVON ذاتي الاستضافة</b></div><span>{status?.self_hosted_configured?'متصل':'غير متصل'}</span><small>{settings?.runtime_mode||'وضع التشغيل غير معروف'}</small></div>
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
            <div><span>التنفيذ</span><b>{executorLabel(executorState)}</b><small>لا يعتبر منفّذ الأمن متصلًا من دون موصل تنفيذ حقيقي.</small></div>
            <div><span>الأدلة</span><b>{receipts.length} إيصالات</b><small>أي ادعاء تنفيذ يتطلب أدلة مسجلة.</small></div>
            <div><span>تحكم المالك</span><b>إلزامي</b><small>توسيع النطاق يتطلب موافقة جديدة.</small></div>
          </div>
          <div className="admin-panel">
            <div className="panel-head"><div><span className="eyebrow">المهام الأمنية</span><h3>النطاقات المصرّح بها</h3></div></div>
            <div className="security-mission-list">{securityTasks.length?securityTasks.map(t=><button key={t.id} onClick={()=>{setSelectedTask(t.id);setTab('missions')}}><div><b>{t.title||'مهمة أمنية'}</b><small>{short(t.id,14)}</small></div><span>{phaseLabel(t.phase)} · {outcomeLabel(t.outcome)}</span></button>):<div className="empty-panel">لا توجد مهام أمنية مصرّح بها مسجلة.</div>}</div>
          </div>
        </section>
      </>}

      {tab==='runtime'&&<section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">التشغيل</span><h3>محرك AQLEVON والسياسة</h3><p>المحرك الوحيد هو AQLEVON ذاتي الاستضافة.</p></div></div>{settings&&<div className="form-grid"><label>وضع التشغيل<input value="self_hosted_only" disabled/></label><label>درجة الإبداع<input type="number" min="0" max="2" step="0.1" value={settings.temperature??0.6} onChange={e=>setSettings({...settings,temperature:Number(e.target.value)})}/></label><label>سياق المحادثة<input type="number" min="4" max="64" value={settings.max_history||16} onChange={e=>setSettings({...settings,max_history:Number(e.target.value)})}/></label><label className="switch-row"><input type="checkbox" checked={!!settings.verification_enabled} onChange={e=>setSettings({...settings,verification_enabled:e.target.checked})}/><span><b>التحقق الرسمي</b></span></label><label className="switch-row"><input type="checkbox" checked={!!settings.deep_reasoning_enabled} onChange={e=>setSettings({...settings,deep_reasoning_enabled:e.target.checked})}/><span><b>الاستدلال العميق</b></span></label></div>}<div className="status-list"><div><span>محرك AQLEVON</span><b>{status?.self_hosted_configured?'متصل':'غير موصول بعد'}</b></div><div><span>وضع التشغيل</span><b>self_hosted_only</b></div><div><span>الميزانية المدفوعة اليومية</span><b>$0</b></div></div><button className="primary-btn fit" onClick={saveRuntime} disabled={busy}>حفظ الإعدادات</button></div><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">العمليات</span><h3>حقيقة تنفيذ الإجراءات</h3></div></div><div className="status-list"><div><span>المهام</span><b>{tasks.length}</b></div><div><span>نيات التنفيذ</span><b>{intents.length}</b></div><div><span>المحاولات</span><b>{attempts.length}</b></div><div><span>الإيصالات</span><b>{receipts.length}</b></div></div></div></section>}

      {tab==='evaluation'&&<><section className="panel-grid"><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">التقييم</span><h3>قياس AQLEVON</h3><p>يشغّل تقييمًا واحدًا على محرك AQLEVON فقط ضمن بوابة التقييم.</p></div></div><div className="status-list"><div><span>AQLEVON ذاتي الاستضافة</span><b>{status?.self_hosted_configured?'جاهز':'غير موصول بعد'}</b></div><div><span>مرشحات التدريب</span><b>{candidates.length}</b></div><div><span>معتمدة</span><b>{approved.length}</b></div></div><button className="primary-btn fit" onClick={runBenchmark} disabled={busy}>تشغيل تقييم واحد</button></div><div className="admin-panel"><div className="panel-head"><div><span className="eyebrow">التحقق</span><h3>الحقيقة قبل الترقية</h3></div></div><div className="status-list"><div><span>تتبّعات موثقة</span><b>{verified}</b></div><div><span>مؤهلة للتعلّم</span><b>{eligible.length}</b></div><div><span>إيصالات الأدلة</span><b>{receipts.length}</b></div><div><span>محاولات غير محسومة</span><b>{attempts.filter(a=>a.outcome==='UNKNOWN').length}</b></div></div></div></section></>}

      {tab==='learning'&&<><section className="admin-panel wide"><div className="panel-head"><div><span className="eyebrow">بوابة التعلّم الآمن</span><h3>التتبّعات المؤهلة للتعلّم</h3><p>التوثيق وحده لا يغيّر مجموعة التدريب. الترقية تحتاج قرار المالك من هنا.</p></div></div><div className="table-list">{eligible.length?eligible.slice(0,40).map(x=>{const promoted=promotedIds.has(String(x.id));return <div className="table-row" key={x.id}><div><b>{domainNames[traceDomain(x)]||traceDomain(x)} · {x.difficulty||'—'}</b><span>{x.provider||'—'} · {x.model||'—'} · {x.model_calls||1} استدعاءات</span></div><span>{verificationLabel(x.verification)}</span><span>{x.latency_ms?`${x.latency_ms}ms`:'—'}</span><button className="primary-btn fit" disabled={busy||promoted} onClick={()=>promoteTrace(x.id)}>{promoted?'تمت الترقية':'ترقية للتعلم'}</button></div>}):<div className="empty-panel">لا توجد تتبّعات موثقة مؤهلة حاليًا.</div>}</div></section><section className="admin-panel wide"><div className="panel-head"><div><span className="eyebrow">مراجعة التدريب</span><h3>مراجعة مرشحات التدريب</h3><p>لا يصبح المثال معتمدًا إلا بعد قرار المالك.</p></div></div><div className="table-list">{candidates.length?candidates.slice(0,50).map(x=><div className="table-row" key={x.id}><div><b>{String(x.user_input||'').slice(0,90)||'مثال تدريب'}</b><span>{(x.tags||[]).join(' · ')}</span></div><span>{qualityLabel(x.quality_status)}</span><div style={{display:'flex',gap:8}}><button className="primary-btn fit" disabled={busy} onClick={()=>reviewExample(x.id,'approved')}>اعتماد</button><button className="ghost-fit" disabled={busy} onClick={()=>reviewExample(x.id,'rejected')}>رفض</button></div></div>):<div className="empty-panel">لا توجد مرشحات تدريب تنتظر المراجعة.</div>}</div></section></>}
    </main>
  </div>;
}