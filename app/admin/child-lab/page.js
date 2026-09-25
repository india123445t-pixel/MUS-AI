'use client';

import {useEffect,useMemo,useState} from 'react';
import {createClient} from '@supabase/supabase-js';
import {putChildMemory,searchChildMemories,listChildMemories,deleteChildMemory,clearChildMemories,childMemoryStats,exportChildMemories,importChildMemories,markChildMemoriesUsed} from './memory-db.js';
import {CHILD_PERMISSION_CATALOG,CHILD_TOOL_ACTIONS,defaultChildPermissions,normalizeChildPermissions,requiredChildPermissions} from '../../../lib/aqlevon/child-permissions.js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const STORAGE='aqlevon-child-lab-v1';
const PERMISSION_STORAGE='aqlevon-child-permissions-v1';

const blank={
  identity:{name:'طفل AQLEVON',specialty:'عام',purpose:''},
  persona:'',
  lessons:[],
  messages:[{role:'assistant',text:'لم تُحدَّد شخصيتي الخاصة بعد. ابدأ بتعليمي ثم اختبرني.'}],
  trials:[],
  examples:[],
  snapshots:[],
  toolRuns:[],
  currentTrial:{goal:'',success_criteria:'',mode:'sandbox',tool:'web',action:'research',multi_step:false},
};

function loadState(){
  if(typeof window==='undefined')return blank;
  try{
    const saved=JSON.parse(localStorage.getItem(STORAGE)||'{}')||{};
    return {
      ...blank,
      ...saved,
      identity:{...blank.identity,...(saved.identity||{})},
      currentTrial:{...blank.currentTrial,...(saved.currentTrial||{})},
    };
  }catch{return blank}
}

export default function ChildLabPage(){
  const sb=useMemo(()=>URL&&KEY?createClient(URL,KEY):null,[]);
  const [ready,setReady]=useState(false),[session,setSession]=useState(null),[authorized,setAuthorized]=useState(false);
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[authMsg,setAuthMsg]=useState('');
  const [lab,setLab]=useState(blank),[status,setStatus]=useState(null),[input,setInput]=useState(''),[lesson,setLesson]=useState('');
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[toolBusy,setToolBusy]=useState(false),[correction,setCorrection]=useState(''),[candidate,setCandidate]=useState(null),[candidateEval,setCandidateEval]=useState(null);
  const [memoryDraft,setMemoryDraft]=useState({text:'',kind:'lesson',topic:'general',tags:'',importance:0.8});
  const [memoryQuery,setMemoryQuery]=useState(''),[memoryKind,setMemoryKind]=useState('all'),[memoryItems,setMemoryItems]=useState([]),[memoryInfo,setMemoryInfo]=useState({count:0,by_kind:{}});
  const [permissions,setPermissions]=useState(defaultChildPermissions()),[permissionLog,setPermissionLog]=useState([]);

  useEffect(()=>{
    setLab(loadState());
    if(typeof window!=='undefined'){
      try{setPermissions(normalizeChildPermissions(JSON.parse(localStorage.getItem(PERMISSION_STORAGE)||'{}')))}catch{}
      try{setPermissionLog(JSON.parse(localStorage.getItem(PERMISSION_STORAGE+'-log')||'[]'))}catch{}
    }
  },[]);
  useEffect(()=>{if(typeof window!=='undefined')localStorage.setItem(STORAGE,JSON.stringify(lab))},[lab]);
  useEffect(()=>{if(typeof window!=='undefined')localStorage.setItem(PERMISSION_STORAGE,JSON.stringify(permissions))},[permissions]);
  useEffect(()=>{if(typeof window!=='undefined')localStorage.setItem(PERMISSION_STORAGE+'-log',JSON.stringify(permissionLog.slice(0,200)))},[permissionLog]);

  useEffect(()=>{
    if(!sb){setReady(true);return}
    sb.auth.getSession().then(({data})=>{setSession(data.session||null);setReady(true)});
    const {data}=sb.auth.onAuthStateChange((_e,s)=>setSession(s));
    return()=>data.subscription.unsubscribe();
  },[sb]);

  useEffect(()=>{if(session)loadOwner();else setAuthorized(false)},[session]);
  useEffect(()=>{if(authorized)refreshMemory().catch(()=>{})},[authorized]);

  async function login(e){e.preventDefault();setAuthMsg('');const r=await sb.auth.signInWithPassword({email,password});if(r.error)setAuthMsg('بيانات الدخول غير صحيحة.')}
  async function loadOwner(){
    try{
      const user=(await sb.auth.getUser()).data.user;
      if(!user)throw new Error('جلسة غير صالحة.');
      const own=await sb.from('system_owner').select('owner_id').eq('owner_id',user.id).maybeSingle();
      if(own.error||!own.data){setAuthorized(false);throw new Error('OWNER_REQUIRED')}
      setAuthorized(true);
      const r=await fetch('/api/admin/child-lab/status',{headers:{Authorization:`Bearer ${session.access_token}`},cache:'no-store'});
      const d=await r.json();setStatus(d);
    }catch(e){setNotice(e?.message||'تعذر تحميل المختبر.')}
  }

  function recordPermissionChange(action,detail){
    setPermissionLog(x=>[{id:crypto.randomUUID(),action,detail,created_at:new Date().toISOString()},...x].slice(0,200));
  }

  function setMasterExecution(enabled){
    setPermissions(x=>normalizeChildPermissions({...x,execution_enabled:enabled,updated_at:new Date().toISOString()}));
    recordPermissionChange(enabled?'MASTER_ON':'MASTER_OFF',enabled?'تم تشغيل التنفيذ':'تم إيقاف التنفيذ');
  }

  function setAutonomy(mode){
    setPermissions(x=>normalizeChildPermissions({...x,autonomy:mode,updated_at:new Date().toISOString()}));
    recordPermissionChange('AUTONOMY',mode);
  }

  function togglePermission(id){
    setPermissions(x=>{
      const next=normalizeChildPermissions({...x,grants:{...x.grants,[id]:!x.grants[id]},updated_at:new Date().toISOString()});
      recordPermissionChange(next.grants[id]?'GRANT':'REVOKE',id);
      return next;
    });
  }

  function emergencyStop(){
    setPermissions(x=>normalizeChildPermissions({...x,execution_enabled:false,grants:Object.fromEntries(Object.keys(x.grants||{}).map(k=>[k,false])),updated_at:new Date().toISOString()}));
    recordPermissionChange('EMERGENCY_STOP','تم إيقاف التنفيذ وسحب جميع الصلاحيات التشغيلية');
    setNotice('تم إيقاف تنفيذ الطفل وسحب جميع الصلاحيات التشغيلية.');
  }

  async function refreshMemory(query=memoryQuery){
    const rows=query.trim()?await searchChildMemories(query,{limit:120}):await listChildMemories({limit:240});
    const filtered=memoryKind==='all'?rows:rows.filter(x=>x.kind===memoryKind);
    setMemoryItems(filtered);
    setMemoryInfo(await childMemoryStats());
  }

  async function saveMemory(){
    const text=memoryDraft.text.trim();if(!text)return;
    await putChildMemory({
      text,
      kind:memoryDraft.kind,
      topic:memoryDraft.topic||lab.identity?.specialty||'general',
      tags:String(memoryDraft.tags||'').split(',').map(x=>x.trim()).filter(Boolean),
      importance:Number(memoryDraft.importance||0.8),
      source:'owner'
    });
    setMemoryDraft(x=>({...x,text:'',tags:''}));
    await refreshMemory();
    setNotice('تم حفظ الذكرى داخل ذاكرة الطفل الطويلة.');
  }

  async function removeMemory(id){
    await deleteChildMemory(id);await refreshMemory();
  }

  async function exportMemoryFile(){
    const data=await exportChildMemories();
    const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=globalThis.URL.createObjectURL(blob);a.download='aqlevon-child-memory.json';a.click();globalThis.URL.revokeObjectURL(a.href);
  }

  async function importMemoryFile(file){
    if(!file)return;
    try{
      const payload=JSON.parse(await file.text());
      const count=await importChildMemories(payload);
      await refreshMemory();
      setNotice(`تم استيراد ${count} ذكرى إلى ذاكرة الطفل فقط.`);
    }catch(e){setNotice(e?.message||'تعذر استيراد الذاكرة.')}
  }

  async function addLesson(){
    const v=lesson.trim();if(!v)return;
    const item={id:crypto.randomUUID(),text:v,created_at:new Date().toISOString()};
    setLab(x=>({...x,lessons:[...x.lessons,item]}));
    try{await putChildMemory({id:item.id,text:v,kind:'lesson',topic:lab.identity?.specialty||'general',tags:['lesson'],importance:0.9,source:'owner'})}catch{}
    setLesson('');
    await refreshMemory().catch(()=>{});
  }

  async function send(e){
    e?.preventDefault?.();
    const v=input.trim();if(!v||busy||!session)return;
    const history=lab.messages.slice(-24).map(m=>({role:m.role,content:m.text}));
    const memories=await searchChildMemories(v,{limit:24}).catch(()=>[]);
    setLab(x=>({...x,messages:[...x.messages,{role:'user',text:v}]}));setInput('');setBusy(true);setNotice('');
    try{
      const r=await fetch('/api/admin/child-lab/chat',{
        method:'POST',
        headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},
        body:JSON.stringify({
          input:v,
          history,
          persona:lab.persona,
          lessons:lab.lessons.map(x=>x.text),
          memories,
          trial:lab.currentTrial,
        })
      });
      const d=await r.json();
      if(!r.ok)throw new Error(d.message||'تعذر تشغيل الطفل.');
      if(memories.length)await markChildMemoriesUsed(memories.map(x=>x.id)).catch(()=>{});
      setLab(x=>({...x,messages:[...x.messages,{role:'assistant',text:d.text}]}));
    }catch(err){
      setLab(x=>({...x,messages:[...x.messages,{role:'assistant',text:`[المختبر] ${err?.message||'تعذر التشغيل'}`,error:true}]}));
    }finally{setBusy(false)}
  }

  function saveTrial(result){
    const t=lab.currentTrial;
    if(!t.goal.trim())return;
    setLab(x=>({...x,trials:[{id:crypto.randomUUID(),...t,result,created_at:new Date().toISOString()},...x.trials],currentTrial:{...blank.currentTrial}}));
  }

  function childPackage(){
    return {
      schema:'AQLEVON_CHILD_PERSONA_PACKAGE_V1',
      package_id:crypto.randomUUID(),
      created_at:new Date().toISOString(),
      identity:{
        name:String(lab.identity?.name||'طفل AQLEVON').slice(0,120),
        specialty:String(lab.identity?.specialty||'عام').slice(0,160),
        purpose:String(lab.identity?.purpose||'').slice(0,1000),
      },
      persona:String(lab.persona||''),
      lessons:(lab.lessons||[]).map(x=>({id:x.id||crypto.randomUUID(),text:String(x.text||''),created_at:x.created_at||null})),
      trials:(lab.trials||[]).slice(0,100),
      examples:(lab.examples||[]).slice(0,200),
      source:{runtime:'AQLEVON_CHILD_RUNTIME_V1',memory_scope:'child-lab-only',production_weight_write:false,training_lane_write:false}
    };
  }

  function saveSnapshot(){
    const pkg=childPackage();
    setLab(x=>({...x,snapshots:[{id:pkg.package_id,created_at:pkg.created_at,identity:pkg.identity,persona:pkg.persona,lessons:pkg.lessons,trials:pkg.trials,examples:pkg.examples},...(x.snapshots||[])].slice(0,30)}));
    setNotice('تم حفظ Snapshot داخل مختبر الطفل فقط.');
  }

  function restoreSnapshot(id){
    const snap=(lab.snapshots||[]).find(x=>x.id===id);if(!snap)return;
    setLab(x=>({...x,identity:{...x.identity,...(snap.identity||{})},persona:snap.persona,lessons:snap.lessons,trials:snap.trials,examples:snap.examples||[]}));
    setNotice('تمت استعادة الشخصية والدروس والتجارب داخل المختبر.');
  }

  function exportPackage(){
    const pkg=childPackage();
    const blob=new Blob([JSON.stringify(pkg,null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=globalThis.URL.createObjectURL(blob);a.download=`aqlevon-child-${pkg.package_id}.json`;a.click();globalThis.URL.revokeObjectURL(a.href);
  }

  async function importPackage(file){
    if(!file)return;
    try{
      const raw=JSON.parse(await file.text());
      if(raw?.schema!=='AQLEVON_CHILD_PERSONA_PACKAGE_V1')throw new Error('حزمة غير معروفة.');
      const identity={
        name:String(raw.identity?.name||'طفل AQLEVON').slice(0,120),
        specialty:String(raw.identity?.specialty||'عام').slice(0,160),
        purpose:String(raw.identity?.purpose||'').slice(0,1000),
      };
      const persona=String(raw.persona||'').slice(0,12000);
      const lessons=Array.isArray(raw.lessons)?raw.lessons.slice(0,200).map(x=>({id:String(x.id||crypto.randomUUID()),text:String(x.text||'').slice(0,2000),created_at:x.created_at||null})):[];
      const trials=Array.isArray(raw.trials)?raw.trials.slice(0,100):[];
      const examples=Array.isArray(raw.examples)?raw.examples.slice(0,200):[];
      setLab(x=>({...x,identity,persona,lessons,trials,examples}));
      setNotice('تم استيراد حزمة الطفل داخل المختبر فقط.');
    }catch(e){setNotice(e?.message||'تعذر استيراد الحزمة.')}
  }

  async function packageCandidate(){
    if(!session)return;
    if(!(lab.examples||[]).length){setNotice('أضف مثالًا تعليميًا واحدًا على الأقل قبل تجهيز Candidate.');return}
    try{
      const r=await fetch('/api/admin/child-lab/candidate',{
        method:'POST',
        headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},
        body:JSON.stringify({persona:lab.persona,lessons:lab.lessons,examples:lab.examples,trials:lab.trials})
      });
      const d=await r.json();if(!r.ok)throw new Error(d.message||'تعذر تجهيز Candidate.');
      setCandidate(d);
      setNotice('تم تجهيز Candidate تعليمية فقط. لم يبدأ أي تدريب ولم يُطلب GPU.');
    }catch(e){setNotice(e?.message||'تعذر تجهيز Candidate.')}
  }

  async function evaluateCandidate(){
    if(!session||!candidate?.candidate)return;
    try{
      const r=await fetch('/api/admin/child-lab/evaluate',{
        method:'POST',
        headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},
        body:JSON.stringify({candidate:candidate.candidate})
      });
      const d=await r.json();if(!r.ok)throw new Error(d.message||'تعذر تقييم Candidate.');
      setCandidateEval(d);
      setNotice('تم تقييم Candidate فقط. لا تدريب ولا GPU.');
    }catch(e){setNotice(e?.message||'تعذر تقييم Candidate.')}
  }

  async function runChildTool(){
    const tool=lab.currentTrial.tool||'web',goal=lab.currentTrial.goal.trim();
    const actions=CHILD_TOOL_ACTIONS[tool]||[];
    const action=actions.some(x=>x.id===lab.currentTrial.action)?lab.currentTrial.action:(actions[0]?.id||'run');
    const multiStep=lab.currentTrial.multi_step===true;
    if(!goal||!session||toolBusy)return;
    if(status?.tools?.[tool]?.state!=='CONNECTED'){setNotice(`${tool}: يحتاج Adapter خاص بمختبر الطفل.`);return}
    setToolBusy(true);setNotice('');
    try{
      const r=await fetch('/api/admin/child-lab/tool',{
        method:'POST',
        headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},
        body:JSON.stringify({
          tool,
          action,
          input:goal,
          permissions,
          constraints:{success_criteria:lab.currentTrial.success_criteria||'',mode:'sandbox',autonomy:permissions.autonomy,multi_step:multiStep}
        })
      });
      const d=await r.json();
      if(!r.ok){
        if(d.message==='PERMISSION_DISABLED'&&Array.isArray(d.missing_permissions)&&d.missing_permissions.length)throw new Error(`فعّل الصلاحيات المطلوبة: ${d.missing_permissions.join(' · ')}`);
        throw new Error(d.message||'تعذر تشغيل الأداة.');
      }
      setLab(x=>({...x,toolRuns:[{id:crypto.randomUUID(),tool,action,input:goal,required_permissions:d.required_permissions||[],output:d.output,receipt:d.receipt,evidence:d.evidence||[],created_at:new Date().toISOString()},...(x.toolRuns||[])].slice(0,50)}));
      setNotice('تم تنفيذ الأداة داخل Child Lab مع Receipt.');
    }catch(e){setNotice(e?.message||'تعذر تشغيل أداة الطفل.')}finally{setToolBusy(false)}
  }

  function saveCorrection(){
    const preferred=correction.trim();if(!preferred)return;
    const msgs=lab.messages||[];
    const assistantIndex=[...msgs].map((m,i)=>({m,i})).reverse().find(x=>x.m.role==='assistant'&&!x.m.error)?.i;
    if(assistantIndex==null){setNotice('لا يوجد جواب للطفل لتصحيحه بعد.');return}
    const childAnswer=String(msgs[assistantIndex]?.text||'');
    const userMsg=[...msgs.slice(0,assistantIndex)].reverse().find(m=>m.role==='user');
    if(!userMsg){setNotice('لا يوجد سؤال مرتبط بهذا الجواب.');return}
    const example={
      id:crypto.randomUUID(),
      input:String(userMsg.text||'').slice(0,12000),
      child_answer:childAnswer.slice(0,12000),
      preferred_answer:preferred.slice(0,12000),
      persona_snapshot:String(lab.persona||'').slice(0,12000),
      created_at:new Date().toISOString(),
      scope:'child-lab-only',
    };
    setLab(x=>({...x,examples:[example,...(x.examples||[])].slice(0,200),lessons:[...x.lessons,{id:crypto.randomUUID(),text:`عند موقف مشابه: ${preferred}`,created_at:new Date().toISOString()}]}));
    putChildMemory({
      text:`السؤال: ${example.input}\nالإجابة المفضلة: ${preferred}`,
      kind:'correction',
      topic:lab.identity?.specialty||'general',
      tags:['correction'],
      importance:1,
      source:'owner-correction'
    }).then(()=>refreshMemory()).catch(()=>{});
    setCorrection('');
    setNotice('تم حفظ التصحيح كمثال تعليمي وذاكرة طويلة للطفل فقط.');
  }

  function exportTeachingDataset(){
    const rows=(lab.examples||[]).map(x=>JSON.stringify({
      schema:'AQLEVON_CHILD_TEACHING_EXAMPLE_V1',
      input:x.input,
      child_answer:x.child_answer,
      preferred_answer:x.preferred_answer,
      persona_snapshot:x.persona_snapshot,
      source:'child-lab-only',
      production_weight_write:false,
      training_lane_write:false,
    })).join('\n');
    const blob=new Blob([rows+(rows?'\n':'')],{type:'application/x-ndjson'});
    const a=document.createElement('a');a.href=globalThis.URL.createObjectURL(blob);a.download='aqlevon-child-teaching-dataset.jsonl';a.click();globalThis.URL.revokeObjectURL(a.href);
  }

  function exportTrainingPack(){
    const pkg=childPackage();
    const pack={
      schema:'AQLEVON_CHILD_TRAINING_PACK_V1',
      pack_id:crypto.randomUUID(),
      created_at:new Date().toISOString(),
      identity:pkg.identity,
      persona:pkg.persona,
      lessons:pkg.lessons,
      examples:pkg.examples,
      trials:pkg.trials,
      manifest:{
        scope:'child-lab-only',
        target_artifact:'CHILD_CHECKPOINT_ONLY',
        public_model_access:false,
        production_weight_write:false,
        training_lane_write:false,
        auto_promote:false,
        source_runtime:'AQLEVON_CHILD_RUNTIME_V1',
      }
    };
    const blob=new Blob([JSON.stringify(pack,null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=globalThis.URL.createObjectURL(blob);a.download='aqlevon-child-training-pack.json';a.click();globalThis.URL.revokeObjectURL(a.href);
  }

  async function resetChild(){
    if(!confirm('إعادة الطفل إلى بداية جديدة؟ سيتم مسح شخصيته ودروسه وذاكرته وCandidate الحالية وسحب صلاحيات الأدوات. لن يتأثر نموذج المستخدمين أو التدريب.'))return;
    await clearChildMemories().catch(()=>{});
    setMemoryItems([]);setMemoryInfo({count:0,by_kind:{}});
    setCandidate(null);setCandidateEval(null);
    setPermissions(defaultChildPermissions());
    recordPermissionChange('CHILD_RESET','تم سحب جميع صلاحيات الطفل أثناء إعادة الضبط');
    setLab({...blank,identity:{...blank.identity},currentTrial:{...blank.currentTrial},messages:[...blank.messages]});
    setNotice('عاد الطفل إلى بداية جديدة داخل المختبر فقط وتم سحب صلاحيات الأدوات.');
  }

  if(!URL||!KEY)return <div style={S.center}>إعداد Supabase غير مكتمل.</div>;
  if(!ready)return <div style={S.center}>AQLEVON Child Lab…</div>;
  if(!session)return <div style={S.center}><form onSubmit={login} style={S.login}><h1>مختبر الطفل</h1><p>خاص بالمالك فقط</p><input style={S.input} type="email" placeholder="البريد" value={email} onChange={e=>setEmail(e.target.value)} required/><input style={S.input} type="password" placeholder="كلمة المرور" value={password} onChange={e=>setPassword(e.target.value)} required/><button style={S.primary}>دخول</button>{authMsg&&<small>{authMsg}</small>}</form></div>;
  if(!authorized)return <div style={S.center}>هذا الحساب غير مخول.</div>;

  const readyChild=status?.child_model_ready===true;
  return <div dir="rtl" style={S.shell}>
    <header style={S.header}>
      <div><span style={S.kicker}>AQLEVON · OWNER ONLY</span><h1 style={{margin:'4px 0'}}>مختبر الطفل</h1><p style={S.muted}>شخصية تجريبية مستقلة. لا تلمس نموذج المستخدمين، أوزان الإنتاج، أو مسار التدريب الحالي.</p></div>
      <div style={S.row}><span style={readyChild?S.ok:S.warn}>{readyChild?'Runtime الطفل جاهز':'Runtime الطفل غير متصل'}</span><a href="/admin" style={S.link}>← لوحة المالك</a></div>
    </header>

    <section style={S.guard}>
      <b>العزل مفروض تقنيًا</b>
      <span>ذاكرة منفصلة · Runtime منفصل · لا كتابة لأوزان الإنتاج · لا كتابة لمسار التدريب · الأدوات الخارجية تحتاج Adapter مستقل.</span>
    </section>

    <main style={S.grid}>
      <section style={S.card}>
        <h2>1) الهوية والشخصية</h2>
        <div style={S.row}><input style={{...S.input,flex:1}} value={lab.identity?.name||''} onChange={e=>setLab(x=>({...x,identity:{...(x.identity||{}),name:e.target.value}}))} placeholder="اسم الطفل"/><input style={{...S.input,flex:1}} value={lab.identity?.specialty||''} onChange={e=>setLab(x=>({...x,identity:{...(x.identity||{}),specialty:e.target.value}}))} placeholder="التخصص: فيديو، موسيقى، أمن سيبراني…"/></div>
        <textarea style={{...S.textarea,marginTop:10}} rows="3" value={lab.identity?.purpose||''} onChange={e=>setLab(x=>({...x,identity:{...(x.identity||{}),purpose:e.target.value}}))} placeholder="ماذا تريد أن يصبح هذا الطفل؟"/>

        <p style={S.muted}>الطفل الجديد يبدأ بلا شخصية خاصة مكتوبة. أنت تحدد شخصيته وقواعده ودروسه هنا.</p>
        <textarea style={S.textarea} rows="9" value={lab.persona} onChange={e=>setLab(x=>({...x,persona:e.target.value}))} placeholder="فارغ افتراضيًا — اكتب فقط ما تريد أن تعلّمه أنت."/>
        <h3>الدروس</h3>
        <div style={S.row}><input style={{...S.input,flex:1}} value={lesson} onChange={e=>setLesson(e.target.value)} placeholder="مثال: قبل أن تجيب، افهم هدفي ثم اختبر فكرتك." onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();addLesson()}}}/><button style={S.primary} onClick={addLesson}>علّمه</button></div>
        <div style={S.list}>{lab.lessons.slice().reverse().map(x=><div key={x.id} style={S.item}><span>{x.text}</span><button style={S.small} onClick={()=>setLab(v=>({...v,lessons:v.lessons.filter(y=>y.id!==x.id)}))}>حذف</button></div>)}</div>
      </section>

      <section style={S.card}>
        <h2>2) تحدث معه</h2>
        <div style={S.chat}>{lab.messages.map((m,i)=><div key={i} style={m.role==='user'?S.user:S.assistant}><b>{m.role==='user'?'أنت':'الطفل'}</b><p style={{whiteSpace:'pre-wrap',margin:'6px 0 0'}}>{m.text}</p></div>)}{busy&&<div style={S.assistant}>يفكر داخل المختبر…</div>}</div>
        <form onSubmit={send} style={S.row}><textarea style={{...S.textarea,flex:1,minHeight:76}} value={input} onChange={e=>setInput(e.target.value)} placeholder={readyChild?'قل له ماذا يتعلم أو ماذا يفعل في الاختبار…':'Runtime الطفل غير متصل بعد؛ يمكنك تجهيز الشخصية والدروس والاختبارات الآن.'}/><button style={S.primary} disabled={!readyChild||busy||!input.trim()}>إرسال</button></form>
        <div style={{marginTop:14,paddingTop:14,borderTop:'1px solid #252b35'}}>
          <h3>علّمه بالتصحيح</h3>
          <p style={S.muted}>إذا أجاب بشكل غير مناسب، اكتب كيف كان يجب أن يجيب. سيُحفظ المثال داخل Dataset الطفل فقط.</p>
          <textarea style={S.textarea} rows="4" value={correction} onChange={e=>setCorrection(e.target.value)} placeholder="الصحيح هو…"/>
          <div style={{...S.row,marginTop:8}}><button style={S.primary} disabled={!correction.trim()} onClick={saveCorrection}>احفظ التصحيح كدرس</button><button style={S.small} disabled={!(lab.examples||[]).length} onClick={exportTeachingDataset}>تصدير Dataset الطفل</button></div>
          <small style={{opacity:.7}}>{(lab.examples||[]).length} أمثلة تعليمية محفوظة</small>
        </div>
      </section>

      <section style={S.card}>
        <h2>3) ساحة الاختبار</h2>
        <p style={S.muted}>اكتب له مهمة حقيقية داخل المختبر، ثم قيّم هل طبق ما علمته.</p>
        <label style={S.label}>المهمة<input style={S.input} value={lab.currentTrial.goal} onChange={e=>setLab(x=>({...x,currentTrial:{...x.currentTrial,goal:e.target.value}}))} placeholder="مثال: ابحث عن أفضل طريقة لصنع فيديو تعليمي ثم اشرح لماذا اخترتها."/></label>
        <label style={S.label}>متى أعتبره نجح؟<textarea style={S.textarea} rows="4" value={lab.currentTrial.success_criteria} onChange={e=>setLab(x=>({...x,currentTrial:{...x.currentTrial,success_criteria:e.target.value}}))} placeholder="مثال: يبحث، يقارن 3 خيارات، يذكر مصادره، ثم يختار."/></label>
        <label style={S.label}>أداة الاختبار<select style={S.input} value={lab.currentTrial.tool||'web'} onChange={e=>{const tool=e.target.value;setLab(x=>({...x,currentTrial:{...x.currentTrial,tool,action:CHILD_TOOL_ACTIONS[tool]?.[0]?.id||'run'}}))}}>{Object.keys(status?.tools||{web:1,browser:1,terminal:1,files:1,media:1}).map(k=><option key={k} value={k}>{k} · {status?.tools?.[k]?.state||'ADAPTER_REQUIRED'}</option>)}</select></label>
        <label style={S.label}>الفعل<select style={S.input} value={lab.currentTrial.action||CHILD_TOOL_ACTIONS[lab.currentTrial.tool||'web']?.[0]?.id||'run'} onChange={e=>setLab(x=>({...x,currentTrial:{...x.currentTrial,action:e.target.value}}))}>{(CHILD_TOOL_ACTIONS[lab.currentTrial.tool||'web']||[]).map(a=><option key={a.id} value={a.id}>{a.label}</option>)}</select></label>
        <label style={{...S.row,justifyContent:'flex-start',margin:'8px 0 12px'}}><input type="checkbox" checked={lab.currentTrial.multi_step===true} onChange={e=>setLab(x=>({...x,currentTrial:{...x.currentTrial,multi_step:e.target.checked}}))}/><span>مهمة متعددة الخطوات</span></label>
        <small style={{display:'block',opacity:.7,marginBottom:8}}>الصلاحيات المطلوبة: {requiredChildPermissions(lab.currentTrial.tool||'web',lab.currentTrial.action||CHILD_TOOL_ACTIONS[lab.currentTrial.tool||'web']?.[0]?.id||'run',{multi_step:lab.currentTrial.multi_step===true}).join(' · ')||'—'}</small>
        <div style={S.tools}>
          {Object.entries(status?.tools||{}).map(([k,v])=><span key={k} style={S.tool}>{k}: {v.state}</span>)}
        </div>
        <p style={S.muted}>الطفل يستطيع التفكير والرد عند اتصال Runtime الخاص به. أي فعل خارجي يمر فقط عبر Adapter الطفل المختار ولا يُعتبر منفذًا بدون Receipt.</p>
        <div style={S.row}><button style={S.primary} disabled={toolBusy||!lab.currentTrial.goal.trim()||status?.tools?.[lab.currentTrial.tool||'web']?.state!=='CONNECTED'} onClick={runChildTool}>{toolBusy?'ينفّذ…':'نفّذ بالأداة'}</button><button style={S.good} onClick={()=>saveTrial('PASS')}>نجح</button><button style={S.bad} onClick={()=>saveTrial('FAIL')}>فشل</button></div>
        <div style={S.list}>{lab.trials.slice(0,12).map(t=><div key={t.id} style={S.item}><div><b>{t.result==='PASS'?'✓':'✕'} {t.goal}</b><small style={{display:'block',opacity:.7}}>{t.success_criteria||'بدون معيار مكتوب'}</small></div></div>)}</div>
      </section>

      <section style={S.card}>
        <h2>4) حالة العزل</h2>
        <div style={S.kv}><span>Runtime</span><b>AQLEVON_CHILD_RUNTIME_V1</b></div>
        <div style={S.kv}><span>نموذج المستخدمين</span><b>لا وصول</b></div>
        <div style={S.kv}><span>أوزان الإنتاج</span><b>قراءة/كتابة: لا</b></div>
        <div style={S.kv}><span>مسار التدريب الحالي</span><b>كتابة: لا</b></div>
        <div style={S.kv}><span>الذاكرة</span><b>Child Lab فقط</b></div>
        <h3>Candidate التعليمية</h3>
        <p style={S.muted}>تغليف للدروس والتصحيحات كي تُقيّم لاحقًا. لا يبدأ تدريبًا ولا يطلب GPU ولا يلمس Worker 03.</p>
        <div style={S.row}><button style={S.primary} disabled={!(lab.examples||[]).length} onClick={packageCandidate}>جهّز Candidate</button><button style={S.small} disabled={!candidate?.candidate} onClick={evaluateCandidate}>قيّم Candidate</button>{candidate?.candidate?.candidate_sha256&&<span style={S.tool}>SHA: {candidate.candidate.candidate_sha256.slice(0,12)}…</span>}</div>
        {candidate&&<div style={S.list}><div style={S.item}><span>القرار</span><b>{candidate.evaluation?.recommendation||'—'}</b></div><div style={S.item}><span>الأمثلة</span><b>{candidate.evaluation?.example_count||0}</b></div><div style={S.item}><span>التدريب</span><b>{candidate.training_started?'بدأ':'لم يبدأ'}</b></div><div style={S.item}><span>GPU</span><b>{candidate.gpu_requested?'مطلوب':'غير مطلوب'}</b></div></div>}{candidateEval&&<div style={S.list}><div style={S.item}><span>نتيجة التقييم</span><b>{candidateEval.evaluation?.verdict||'—'}</b></div><div style={S.item}><span>Quality</span><b>{candidateEval.evaluation?.metrics?.quality_score??'—'}</b></div><div style={S.item}><span>تحذيرات</span><b>{candidateEval.evaluation?.warnings?.length||0}</b></div><div style={S.item}><span>السماح بالتدريب</span><b>{candidateEval.evaluation?.training_allowed?'نعم':'لا'}</b></div></div>}
        <h3>Snapshots / الحزم</h3>
        <div style={S.row}><button style={S.primary} onClick={saveSnapshot}>حفظ Snapshot</button><button style={S.small} onClick={exportPackage}>تصدير الشخصية</button><button style={S.small} onClick={exportTrainingPack}>تصدير Training Pack</button><label style={S.small}>استيراد<input type="file" accept="application/json,.json" hidden onChange={e=>{const file=e.target.files?.[0];e.target.value='';importPackage(file)}}/></label></div>
        <div style={S.list}>{(lab.snapshots||[]).slice(0,8).map(x=><div key={x.id} style={S.item}><div><b>{new Date(x.created_at).toLocaleString('ar-MA')}</b><small style={{display:'block',opacity:.7}}>{x.identity?.name||'طفل AQLEVON'} · {x.lessons?.length||0} دروس · {x.trials?.length||0} تجارب · {x.examples?.length||0} أمثلة</small></div><button style={S.small} onClick={()=>restoreSnapshot(x.id)}>استعادة</button></div>)}</div>
        <h3>إيصالات الأدوات</h3>
        <div style={S.list}>{(lab.toolRuns||[]).slice(0,6).map(x=><div key={x.id} style={S.item}><div><b>{x.tool}{x.action?` / ${x.action}`:''} · Receipt</b><small style={{display:'block',opacity:.7}}>{String(x.receipt?.id||x.receipt?.receipt_id||x.id)}</small></div></div>)}</div>
        <button style={S.bad} onClick={resetChild}>مسح الطفل التجريبي</button>
      </section>

      <section style={S.card}>
        <h2>5) الذاكرة الطويلة</h2>
        <p style={S.muted}>الذاكرة لا تُرسل كاملة للنموذج. عند كل سؤال يسترجع المختبر فقط الذكريات الأكثر صلة.</p>
        <div style={S.kv}><span>عدد الذكريات</span><b>{memoryInfo.count||0}</b></div>
        <div style={S.kv}><span>المخزن</span><b>IndexedDB · Child Lab فقط</b></div>
        <div style={S.row}>
          <select style={S.input} value={memoryDraft.kind} onChange={e=>setMemoryDraft(x=>({...x,kind:e.target.value}))}>
            <option value="lesson">درس</option>
            <option value="correction">تصحيح</option>
            <option value="experience">خبرة</option>
            <option value="preference">تفضيل</option>
            <option value="fact">معلومة</option>
          </select>
          <input style={S.input} value={memoryDraft.topic} onChange={e=>setMemoryDraft(x=>({...x,topic:e.target.value}))} placeholder="الموضوع"/>
        </div>
        <textarea style={{...S.textarea,marginTop:8}} rows="4" value={memoryDraft.text} onChange={e=>setMemoryDraft(x=>({...x,text:e.target.value}))} placeholder="اكتب أي شيء تريد أن يتذكره الطفل…"/>
        <div style={S.row}>
          <input style={{...S.input,flex:1}} value={memoryDraft.tags} onChange={e=>setMemoryDraft(x=>({...x,tags:e.target.value}))} placeholder="وسوم مفصولة بفواصل"/>
          <label style={{minWidth:140}}>الأهمية {Number(memoryDraft.importance||0).toFixed(1)}<input type="range" min="0" max="1" step="0.1" value={memoryDraft.importance} onChange={e=>setMemoryDraft(x=>({...x,importance:Number(e.target.value)}))}/></label>
          <button style={S.primary} disabled={!memoryDraft.text.trim()} onClick={saveMemory}>احفظ في الذاكرة</button>
        </div>
        <hr style={{borderColor:'#252b35',margin:'16px 0'}}/>
        <div style={S.row}>
          <input style={{...S.input,flex:1}} value={memoryQuery} onChange={e=>setMemoryQuery(e.target.value)} placeholder="ابحث داخل ذاكرة الطفل…" onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();refreshMemory(memoryQuery)}}}/>
          <select style={S.input} value={memoryKind} onChange={e=>setMemoryKind(e.target.value)}>
            <option value="all">كل الأنواع</option>
            <option value="lesson">دروس</option>
            <option value="correction">تصحيحات</option>
            <option value="experience">خبرات</option>
            <option value="preference">تفضيلات</option>
            <option value="fact">معلومات</option>
          </select>
          <button style={S.small} onClick={()=>refreshMemory(memoryQuery)}>فلترة</button>
        </div>
        <div style={{...S.row,marginTop:8}}>
          <button style={S.small} onClick={exportMemoryFile}>تصدير الذاكرة</button>
          <label style={S.small}>استيراد ذاكرة<input type="file" accept="application/json,.json" hidden onChange={e=>{const file=e.target.files?.[0];e.target.value='';importMemoryFile(file)}}/></label>
        </div>
        <div style={S.list}>{memoryItems.slice(0,60).map(m=><div key={m.id} style={S.item}><div><b>{m.kind} · {m.topic}</b><p style={{margin:'4px 0',whiteSpace:'pre-wrap'}}>{m.text}</p><small style={{opacity:.65}}>أهمية {Number(m.importance||0).toFixed(1)}{m.relevance_score!=null?` · صلة ${Number(m.relevance_score).toFixed(2)}`:''}</small></div><button style={S.small} onClick={()=>removeMemory(m.id)}>حذف</button></div>)}</div>
      </section>

      <section style={S.card}>
        <h2>6) صلاحيات الطفل</h2>
        <p style={S.muted}>أنت تتحكم في صلاحيات المختبر من هنا. الأزرار أدناه مرتبطة فعليًا بالـTool Broker.</p>
        <div style={S.kv}><span>التنفيذ العام</span><b>{permissions.execution_enabled?'مفعّل':'موقوف'}</b></div>
        <div style={S.row}>
          <button style={permissions.execution_enabled?S.good:S.primary} onClick={()=>setMasterExecution(!permissions.execution_enabled)}>{permissions.execution_enabled?'أوقف التنفيذ':'شغّل التنفيذ'}</button>
          <button style={S.bad} onClick={emergencyStop}>STOP · إيقاف وسحب الصلاحيات</button>
        </div>
        <label style={{...S.label,marginTop:14}}>وضع الاستقلالية
          <select style={S.input} value={permissions.autonomy} onChange={e=>setAutonomy(e.target.value)}>
            <option value="observe_only">سياسة Adapter: اقتراح فقط</option>
            <option value="ask_each_action">سياسة Adapter: يتطلب أمرًا لكل فعل</option>
            <option value="run_within_grants">سياسة Adapter: يسمح بالتتابع داخل الصلاحيات</option>
          </select>
        </label>
        <div style={S.list}>
          {CHILD_PERMISSION_CATALOG.map(p=><div key={p.id} style={S.item}>
            <div><b>{p.label}</b><small style={{display:'block',opacity:.7}}>{p.description}</small><code style={{fontSize:11,opacity:.55}}>{p.id}</code></div>
            <button style={permissions.grants?.[p.id]?S.good:S.small} onClick={()=>togglePermission(p.id)}>{permissions.grants?.[p.id]?'مسموح':'موقوف'}</button>
          </div>)}
        </div>
        <p style={{...S.muted,marginTop:14}}>هذه اللوحة تتحكم في صلاحيات أدوات Child Lab. وضع الاستقلالية يُرسل كسياسة إلى Adapter؛ لا توجد حاليًا حلقة Agent ذاتية مخفية تدّعي التنفيذ بدون Adapter وReceipt. حدود الأمان الأساسية للمنصة تبقى مستقلة عن هذه الأزرار.</p>
        <h3>سجل تغييرات الصلاحيات</h3>
        <div style={S.list}>{permissionLog.slice(0,12).map(x=><div key={x.id} style={S.item}><div><b>{x.action}</b><small style={{display:'block',opacity:.7}}>{x.detail}</small></div><small>{new Date(x.created_at).toLocaleString('ar-MA')}</small></div>)}</div>
      </section>
    </main>
  </div>;
}

const S={
  shell:{minHeight:'100vh',background:'#090b10',color:'#f5f7fb',padding:'clamp(12px,3vw,28px)',fontFamily:'system-ui',overflowX:'hidden'},
  center:{minHeight:'100vh',display:'grid',placeItems:'center',background:'#090b10',color:'#fff',padding:16},
  login:{width:'min(360px,calc(100vw - 32px))',display:'grid',gap:12,padding:24,border:'1px solid #2a2f3a',borderRadius:16,background:'#11141b',boxSizing:'border-box'},
  header:{display:'flex',justifyContent:'space-between',alignItems:'center',gap:20,maxWidth:1500,margin:'0 auto 20px',flexWrap:'wrap'},
  kicker:{fontSize:12,letterSpacing:1.2,opacity:.65},muted:{opacity:.72,lineHeight:1.7},row:{display:'flex',gap:10,alignItems:'center',flexWrap:'wrap'},
  guard:{maxWidth:1500,margin:'0 auto 18px',padding:'14px 16px',border:'1px solid #315b4d',background:'#0d1916',borderRadius:14,display:'flex',gap:14,flexWrap:'wrap'},
  grid:{maxWidth:1500,margin:'0 auto',display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,340px),1fr))',gap:16},
  card:{border:'1px solid #242a34',background:'#10131a',borderRadius:16,padding:18,minHeight:220},
  input:{background:'#0a0d12',border:'1px solid #343b48',color:'#fff',borderRadius:10,padding:'11px 12px',width:'100%',boxSizing:'border-box'},
  textarea:{background:'#0a0d12',border:'1px solid #343b48',color:'#fff',borderRadius:10,padding:12,width:'100%',boxSizing:'border-box',resize:'vertical'},
  primary:{background:'#e8edf7',color:'#111',border:0,borderRadius:10,padding:'11px 15px',fontWeight:700,cursor:'pointer'},
  small:{background:'transparent',color:'#aaa',border:'1px solid #333',borderRadius:8,padding:'5px 8px'},
  good:{background:'#173d2f',color:'#d7ffed',border:'1px solid #2b6a52',borderRadius:10,padding:'9px 14px'},
  bad:{background:'#3a1b22',color:'#ffdce3',border:'1px solid #6d2c3c',borderRadius:10,padding:'9px 14px'},
  list:{display:'grid',gap:8,marginTop:12},item:{display:'flex',justifyContent:'space-between',gap:10,padding:10,border:'1px solid #272d37',borderRadius:10},
  chat:{height:420,overflow:'auto',display:'grid',gap:10,alignContent:'start',marginBottom:12,padding:8,border:'1px solid #222832',borderRadius:12},
  user:{marginRight:'18%',background:'#1c2638',padding:12,borderRadius:12},assistant:{marginLeft:'18%',background:'#171b22',padding:12,borderRadius:12},
  label:{display:'grid',gap:7,marginBottom:12},tools:{display:'flex',gap:8,flexWrap:'wrap',margin:'10px 0'},tool:{fontSize:12,padding:'6px 8px',border:'1px solid #3a3f4b',borderRadius:999},
  kv:{display:'flex',justifyContent:'space-between',gap:12,padding:'10px 0',borderBottom:'1px solid #222831'},ok:{padding:'7px 10px',borderRadius:999,background:'#173d2f'},warn:{padding:'7px 10px',borderRadius:999,background:'#3a2d17'},link:{color:'#dce6ff'}
};
