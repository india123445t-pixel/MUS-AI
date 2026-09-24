'use client';

import {useEffect,useMemo,useState} from 'react';
import {createClient} from '@supabase/supabase-js';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const STORAGE='aqlevon-child-lab-v1';

const blank={
  persona:'أنت طفل AQLEVON تجريبي. تعلّم من المالك داخل هذا المختبر فقط. اسأل عندما لا تفهم، وطبّق الدروس في التجارب.',
  lessons:[],
  messages:[{role:'assistant',text:'أنا طفل AQLEVON داخل المختبر المستقل. علّمني شيئًا ثم اختبرني.'}],
  trials:[],
  currentTrial:{goal:'',success_criteria:'',mode:'sandbox'},
};

function loadState(){
  if(typeof window==='undefined')return blank;
  try{return {...blank,...JSON.parse(localStorage.getItem(STORAGE)||'{}')}}catch{return blank}
}

export default function ChildLabPage(){
  const sb=useMemo(()=>URL&&KEY?createClient(URL,KEY):null,[]);
  const [ready,setReady]=useState(false),[session,setSession]=useState(null),[authorized,setAuthorized]=useState(false);
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[authMsg,setAuthMsg]=useState('');
  const [lab,setLab]=useState(blank),[status,setStatus]=useState(null),[input,setInput]=useState(''),[lesson,setLesson]=useState('');
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');

  useEffect(()=>{setLab(loadState())},[]);
  useEffect(()=>{if(typeof window!=='undefined')localStorage.setItem(STORAGE,JSON.stringify(lab))},[lab]);

  useEffect(()=>{
    if(!sb){setReady(true);return}
    sb.auth.getSession().then(({data})=>{setSession(data.session||null);setReady(true)});
    const {data}=sb.auth.onAuthStateChange((_e,s)=>setSession(s));
    return()=>data.subscription.unsubscribe();
  },[sb]);

  useEffect(()=>{if(session)loadOwner();else setAuthorized(false)},[session]);

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

  function addLesson(){
    const v=lesson.trim();if(!v)return;
    setLab(x=>({...x,lessons:[...x.lessons,{id:crypto.randomUUID(),text:v,created_at:new Date().toISOString()}]}));
    setLesson('');
  }

  async function send(e){
    e?.preventDefault?.();
    const v=input.trim();if(!v||busy||!session)return;
    const history=lab.messages.slice(-24).map(m=>({role:m.role,content:m.text}));
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
          trial:lab.currentTrial,
        })
      });
      const d=await r.json();
      if(!r.ok)throw new Error(d.message||'تعذر تشغيل الطفل.');
      setLab(x=>({...x,messages:[...x.messages,{role:'assistant',text:d.text}]}));
    }catch(err){
      setLab(x=>({...x,messages:[...x.messages,{role:'assistant',text:`[المختبر] ${err?.message||'تعذر التشغيل'}`,error:true}]}));
    }finally{setBusy(false)}
  }

  function saveTrial(result){
    const t=lab.currentTrial;
    if(!t.goal.trim())return;
    setLab(x=>({...x,trials:[{id:crypto.randomUUID(),...t,result,created_at:new Date().toISOString()},...x.trials],currentTrial:{goal:'',success_criteria:'',mode:'sandbox'}}));
  }

  function resetChild(){
    if(!confirm('مسح ذاكرة ودروس مختبر الطفل فقط؟ لن يتأثر نموذج المستخدمين أو التدريب.'))return;
    setLab(blank);
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
        <h2>1) الشخصية</h2>
        <p style={S.muted}>تكلم معه كأنك تربي طفلًا. اكتب من تريد أن يكون وكيف يتصرف.</p>
        <textarea style={S.textarea} rows="9" value={lab.persona} onChange={e=>setLab(x=>({...x,persona:e.target.value}))}/>
        <h3>الدروس</h3>
        <div style={S.row}><input style={{...S.input,flex:1}} value={lesson} onChange={e=>setLesson(e.target.value)} placeholder="مثال: قبل أن تجيب، افهم هدفي ثم اختبر فكرتك." onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();addLesson()}}}/><button style={S.primary} onClick={addLesson}>علّمه</button></div>
        <div style={S.list}>{lab.lessons.slice().reverse().map(x=><div key={x.id} style={S.item}><span>{x.text}</span><button style={S.small} onClick={()=>setLab(v=>({...v,lessons:v.lessons.filter(y=>y.id!==x.id)}))}>حذف</button></div>)}</div>
      </section>

      <section style={S.card}>
        <h2>2) تحدث معه</h2>
        <div style={S.chat}>{lab.messages.map((m,i)=><div key={i} style={m.role==='user'?S.user:S.assistant}><b>{m.role==='user'?'أنت':'الطفل'}</b><p style={{whiteSpace:'pre-wrap',margin:'6px 0 0'}}>{m.text}</p></div>)}{busy&&<div style={S.assistant}>يفكر داخل المختبر…</div>}</div>
        <form onSubmit={send} style={S.row}><textarea style={{...S.textarea,flex:1,minHeight:76}} value={input} onChange={e=>setInput(e.target.value)} placeholder={readyChild?'قل له ماذا يتعلم أو ماذا يفعل في الاختبار…':'Runtime الطفل غير متصل بعد؛ يمكنك تجهيز الشخصية والدروس والاختبارات الآن.'}/><button style={S.primary} disabled={!readyChild||busy||!input.trim()}>إرسال</button></form>
      </section>

      <section style={S.card}>
        <h2>3) ساحة الاختبار</h2>
        <p style={S.muted}>اكتب له مهمة حقيقية داخل المختبر، ثم قيّم هل طبق ما علمته.</p>
        <label style={S.label}>المهمة<input style={S.input} value={lab.currentTrial.goal} onChange={e=>setLab(x=>({...x,currentTrial:{...x.currentTrial,goal:e.target.value}}))} placeholder="مثال: ابحث عن أفضل طريقة لصنع فيديو تعليمي ثم اشرح لماذا اخترتها."/></label>
        <label style={S.label}>متى أعتبره نجح؟<textarea style={S.textarea} rows="4" value={lab.currentTrial.success_criteria} onChange={e=>setLab(x=>({...x,currentTrial:{...x.currentTrial,success_criteria:e.target.value}}))} placeholder="مثال: يبحث، يقارن 3 خيارات، يذكر مصادره، ثم يختار."/></label>
        <div style={S.tools}>
          {Object.entries(status?.tools||{}).map(([k,v])=><span key={k} style={S.tool}>{k}: {v.state}</span>)}
        </div>
        <p style={S.muted}>الطفل يستطيع التفكير والرد عند اتصال Runtime الخاص به. البحث/المتصفح/الطرفية/الملفات/الوسائط لا تُعتبر منفذة حتى يتصل Adapter حقيقي خاص بالمختبر.</p>
        <div style={S.row}><button style={S.good} onClick={()=>saveTrial('PASS')}>نجح</button><button style={S.bad} onClick={()=>saveTrial('FAIL')}>فشل</button></div>
        <div style={S.list}>{lab.trials.slice(0,12).map(t=><div key={t.id} style={S.item}><div><b>{t.result==='PASS'?'✓':'✕'} {t.goal}</b><small style={{display:'block',opacity:.7}}>{t.success_criteria||'بدون معيار مكتوب'}</small></div></div>)}</div>
      </section>

      <section style={S.card}>
        <h2>4) حالة العزل</h2>
        <div style={S.kv}><span>Runtime</span><b>AQLEVON_CHILD_RUNTIME_V1</b></div>
        <div style={S.kv}><span>نموذج المستخدمين</span><b>لا وصول</b></div>
        <div style={S.kv}><span>أوزان الإنتاج</span><b>قراءة/كتابة: لا</b></div>
        <div style={S.kv}><span>مسار التدريب الحالي</span><b>كتابة: لا</b></div>
        <div style={S.kv}><span>الذاكرة</span><b>Child Lab فقط</b></div>
        <button style={S.bad} onClick={resetChild}>مسح الطفل التجريبي</button>
      </section>
    </main>
  </div>;
}

const S={
  shell:{minHeight:'100vh',background:'#090b10',color:'#f5f7fb',padding:'28px',fontFamily:'system-ui'},
  center:{minHeight:'100vh',display:'grid',placeItems:'center',background:'#090b10',color:'#fff'},
  login:{width:360,display:'grid',gap:12,padding:24,border:'1px solid #2a2f3a',borderRadius:16,background:'#11141b'},
  header:{display:'flex',justifyContent:'space-between',alignItems:'center',gap:20,maxWidth:1500,margin:'0 auto 20px'},
  kicker:{fontSize:12,letterSpacing:1.2,opacity:.65},muted:{opacity:.72,lineHeight:1.7},row:{display:'flex',gap:10,alignItems:'center'},
  guard:{maxWidth:1500,margin:'0 auto 18px',padding:'14px 16px',border:'1px solid #315b4d',background:'#0d1916',borderRadius:14,display:'flex',gap:14,flexWrap:'wrap'},
  grid:{maxWidth:1500,margin:'0 auto',display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(340px,1fr))',gap:16},
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
