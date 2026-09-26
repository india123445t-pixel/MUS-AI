'use client';

import {useEffect,useMemo,useState} from 'react';
import {createClient} from '@supabase/supabase-js';
import {defaultChildPermissions,normalizeChildPermissions} from '../../lib/aqlevon/child-permissions.js';
import {defaultChildOwnerPolicy,normalizeChildOwnerPolicy} from '../../lib/aqlevon/child-owner-policy.js';
import {mergeToolStates} from './merge.js';
import ToolCard from './ToolCard.jsx';
import SetupGuide from './SetupGuide.jsx';
import ActionLog from './ActionLog.jsx';
import PolicyPanel from './PolicyPanel.jsx';
import './workbench.css';

const URL=process.env.NEXT_PUBLIC_SUPABASE_URL||'';
const KEY=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||'';
const PERMISSION_STORAGE='aqlevon-child-permissions-v1';
const OWNER_POLICY_STORAGE='aqlevon-child-owner-policy-v1';

export default function WorkbenchPage(){
  const sb=useMemo(()=>URL&&KEY?createClient(URL,KEY):null,[]);
  const [snapshot,setSnapshot]=useState(null),[guides,setGuides]=useState({}),[logs,setLogs]=useState([]),[busy,setBusy]=useState(''),[error,setError]=useState('');
  const [session,setSession]=useState(null),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[authMsg,setAuthMsg]=useState('');
  const [permissions,setPermissions]=useState(defaultChildPermissions()),[ownerPolicy,setOwnerPolicy]=useState(defaultChildOwnerPolicy());

  useEffect(()=>{
    try{setPermissions(normalizeChildPermissions(JSON.parse(localStorage.getItem(PERMISSION_STORAGE)||'{}')))}catch{}
    try{setOwnerPolicy(normalizeChildOwnerPolicy(JSON.parse(localStorage.getItem(OWNER_POLICY_STORAGE)||'{}')))}catch{}
    fetch('/api/workbench/status',{cache:'no-store'}).then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.message||'تعذر تحميل Workbench.');setSnapshot(d);setGuides(d.guides||{})}).catch(e=>setError(e?.message||'تعذر تحميل Workbench.'));
  },[]);
  useEffect(()=>{if(!sb)return;sb.auth.getSession().then(({data})=>setSession(data.session||null));const {data}=sb.auth.onAuthStateChange((_e,s)=>setSession(s));return()=>data.subscription.unsubscribe()},[sb]);
  useEffect(()=>{if(session)loadLogs()},[session]);

  async function login(e){e.preventDefault();if(!sb)return setAuthMsg('Supabase غير مهيأ.');setAuthMsg('');const {error:err}=await sb.auth.signInWithPassword({email,password});if(err)setAuthMsg(err.message)}
  async function loadLogs(){
    if(!session)return;
    try{const r=await fetch('/api/workbench/logs',{headers:{Authorization:`Bearer ${session.access_token}`},cache:'no-store'});const d=await r.json();if(!r.ok)throw new Error(d.message||'تعذر تحميل السجل.');const nextLogs=d.logs||[];setLogs(nextLogs);const latest=Object.fromEntries(nextLogs.map(row=>[row.tool,row]));setSnapshot(current=>current?{...current,tools:current.tools.map(tool=>latest[tool.name]?{...tool,last_selftest:latest[tool.name]}:tool)}:current)}catch(e){setError(e?.message||'تعذر تحميل السجل.')}
  }
  async function runTest(tool,level){
    if(!session){setError('اختبارات Workbench تتطلب جلسة المالك.');return}
    const key=`${tool}:${level}`;setBusy(key);setError('');
    try{
      const r=await fetch('/api/workbench/selftest',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session.access_token}`},body:JSON.stringify({tool,level,permissions,ownerPolicy})});
      const d=await r.json();if(!r.ok)throw new Error(d.message||'فشل الاختبار.');
      setSnapshot(current=>current?{...current,tools:current.tools.map(x=>x.name===tool?{...x,last_selftest:d}:x)}:current);
      await loadLogs();
    }catch(e){setError(e?.message||'فشل الاختبار.')}finally{setBusy('')}
  }
  const merged=mergeToolStates(snapshot||{tools:[]},{...permissions,owner_policy:ownerPolicy});
  return <main className="wb-shell" dir="rtl" lang="ar"><section className="wb-wrap">
    <header className="wb-hero"><div><span className="wb-kicker">AQLEVON AI</span><h1>AQLEVON Workbench</h1><p>فحص صريح لحالة محوّلات الأدوات، بدون إظهار مفاتيح أو قيم بيئة وبدون ادعاء تنفيذ غير موثق.</p></div><div className="wb-bos">BOS {snapshot?.bos_version||'—'}</div></header>
    {error&&<div className="wb-alert">{error}</div>}
    {!snapshot&&<div className="wb-loading">جارٍ تحميل الحالة…</div>}
    {snapshot&&<section className="wb-grid">{merged.tools.map(tool=><ToolCard key={tool.name} tool={tool} busy={busy.startsWith(`${tool.name}:`)} onTest={runTest}><SetupGuide guide={guides[tool.name]}/></ToolCard>)}</section>}
    {!session&&<section className="wb-panel wb-login"><div className="wb-panel-head"><div><span className="wb-kicker">OWNER</span><h2>دخول المالك للاختبارات والسجل</h2></div></div><form onSubmit={login}><input type="email" placeholder="البريد" value={email} onChange={e=>setEmail(e.target.value)} required/><input type="password" placeholder="كلمة المرور" value={password} onChange={e=>setPassword(e.target.value)} required/><button type="submit">دخول</button>{authMsg&&<small>{authMsg}</small>}</form></section>}
    <section className="wb-bottom"><PolicyPanel policy={ownerPolicy}/><ActionLog logs={logs}/></section>
  </section></main>;
}