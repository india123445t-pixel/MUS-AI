'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { createClient } from '@supabase/supabase-js';

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

function Icon({name,size=18}){
  const common={width:size,height:size,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.8,strokeLinecap:'round',strokeLinejoin:'round','aria-hidden':true};
  const paths={
    plus:<><path d="M12 5v14M5 12h14"/></>,
    chat:<><path d="M21 15a4 4 0 0 1-4 4H8l-5 3 1.7-5A7 7 0 0 1 3 12V8a5 5 0 0 1 5-5h9a4 4 0 0 1 4 4z"/></>,
    settings:<><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.37a1.7 1.7 0 0 0-1 .63 1.7 1.7 0 0 0-.4 1.1V21h-4v-.1A1.7 1.7 0 0 0 8.55 19.3a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.18 15a1.7 1.7 0 0 0-.63-1 1.7 1.7 0 0 0-1.1-.4H2v-4h.1A1.7 1.7 0 0 0 3.7 8.55a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 8 4.18a1.7 1.7 0 0 0 1-.63A1.7 1.7 0 0 0 9.4 2.45V2h4v.1A1.7 1.7 0 0 0 14.45 3.7a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 18.82 8c.15.4.38.75.68 1 .3.26.7.4 1.1.4h.4v4h-.1A1.7 1.7 0 0 0 19.4 15z"/></>,
    send:<><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></>,
    globe:<><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></>,
    menu:<><path d="M4 7h16M4 12h16M4 17h16"/></>,
    logout:<><path d="M10 17l5-5-5-5M15 12H3M14 3h5a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-5"/></>
  };
  return <svg {...common}>{paths[name]||paths.chat}</svg>
}

export default function ChatPage(){
  const sb=useMemo(()=>URL&&KEY?createClient(URL,KEY):null,[]);
  const [ready,setReady]=useState(false),[session,setSession]=useState(null),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[authMsg,setAuthMsg]=useState('');
  const [conversations,setConversations]=useState([]),[conversation,setConversation]=useState(null),[messages,setMessages]=useState([]),[input,setInput]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  const [webSearch,setWebSearch]=useState(false),[status,setStatus]=useState(null),[mobileOpen,setMobileOpen]=useState(false);
  const endRef=useRef(null);

  useEffect(()=>{if(!sb){setReady(true);return} sb.auth.getSession().then(({data})=>{setSession(data.session||null);setReady(true)});const{data}=sb.auth.onAuthStateChange((_e,s)=>setSession(s));return()=>data.subscription.unsubscribe()},[sb]);
  useEffect(()=>{if(session){loadConversations();loadStatus()}else{setConversations([]);setMessages([]);setConversation(null)}},[session]);
  useEffect(()=>{endRef.current?.scrollIntoView({behavior:'smooth'})},[messages,busy]);

  async function loadStatus(){try{const r=await fetch('/api/status',{headers:{Authorization:`Bearer ${session?.access_token||''}`}});if(r.ok){const d=await r.json();setStatus(d);setWebSearch(!!d?.settings?.web_search_default)}}catch{}}
  async function loadConversations(){const {data}=await sb.from('conversations').select('id,title,created_at').order('created_at',{ascending:false}).limit(40);setConversations(data||[])}
  async function openConversation(c){setConversation(c.id);setMobileOpen(false);const {data}=await sb.from('messages').select('id,role,content,provider,created_at').eq('conversation_id',c.id).order('created_at',{ascending:true});setMessages(data||[])}
  function newChat(){setConversation(null);setMessages([]);setInput('');setMobileOpen(false)}

  async function login(e){e.preventDefault();setAuthMsg('');const r=await sb.auth.signInWithPassword({email,password});if(r.error)setAuthMsg(r.error.message?.toLowerCase().includes('invalid login')?'البريد أو كلمة المرور غير صحيحة.':r.error.message)}
  async function signup(){setAuthMsg('');const r=await sb.auth.signUp({email,password,options:{emailRedirectTo:window.location.origin}});if(r.error)return setAuthMsg(r.error.message);setAuthMsg(r.data?.session?'تم إنشاء الحساب.':'تم إنشاء الحساب. افتح رسالة التأكيد ثم سجّل الدخول.')}
  async function reset(){if(!email)return setAuthMsg('اكتب بريدك أولًا.');const r=await sb.auth.resetPasswordForEmail(email,{redirectTo:window.location.origin});setAuthMsg(r.error?r.error.message:'تم إرسال رابط إعادة تعيين كلمة المرور.')}

  async function saveCandidate(text,answer,provider,model){try{const u=(await sb.auth.getUser()).data.user;if(!u)return;const enabled=status?.settings?.save_training_candidates!==false;if(!enabled)return;await sb.from('training_examples').insert({owner_id:u.id,user_input:text,preferred_answer:answer,category:'general',tags:[provider||'unknown',model||'unknown'],quality_status:'candidate',context_snapshot:{provider,model,created_by:'mus-ai-chat'}})}catch{}}

  async function send(){
    const text=input.trim();if(!text||busy)return;setNotice('');setInput('');
    const history=messages.slice(-16).map(({role,content})=>({role,content}));
    const optimistic={id:`u-${Date.now()}`,role:'user',content:text};setMessages(v=>[...v,optimistic]);setBusy(true);
    try{
      const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${session?.access_token||''}`},body:JSON.stringify({input:text,history,webSearch})});
      const d=await r.json();if(!r.ok)throw Error(d.message||'تعذر الوصول إلى MUS AI.');
      const assistant={id:`a-${Date.now()}`,role:'assistant',content:d.text,provider:d.provider,model:d.model};setMessages(v=>[...v,assistant]);await saveCandidate(text,d.text,d.provider,d.model);
      let cid=conversation;
      const u=(await sb.auth.getUser()).data.user;
      if(!cid){const c=await sb.from('conversations').insert({owner_id:u.id,title:text.slice(0,68)}).select('id,title,created_at').single();cid=c.data?.id||null;setConversation(cid);if(c.data)setConversations(v=>[c.data,...v])}
      if(cid)await sb.from('messages').insert([{owner_id:u.id,conversation_id:cid,role:'user',content:text},{owner_id:u.id,conversation_id:cid,role:'assistant',content:d.text,provider:d.provider}]);
      setStatus(s=>s?{...s,last_provider:d.provider,last_model:d.model}:s)
    }catch(e){setNotice(e.message);setMessages(v=>v.filter(m=>m.id!==optimistic.id))}finally{setBusy(false)}
  }

  if(!URL||!KEY)return <div className="center-screen"><div className="error-box">إعداد Supabase غير مكتمل.</div></div>;
  if(!ready)return <div className="center-screen"><div className="brand-loader"><span>M</span><b>MUS AI</b></div></div>;
  if(!session)return <div className="auth-shell"><div className="auth-panel"><div className="brand-lockup"><div className="brand-mark">M</div><div><strong>MUS AI</strong><span>Intelligence that improves</span></div></div><div className="auth-copy"><h1>مرحبًا بعودتك</h1><p>ادخل إلى MUS AI وتابع محادثاتك ونموذجك الذي يتطور مع الوقت.</p></div><form onSubmit={login} className="auth-form"><label>البريد الإلكتروني<input type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="name@example.com" required/></label><label>كلمة المرور<input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="••••••••" minLength="6" required/></label><button className="primary-btn" type="submit">تسجيل الدخول</button><button type="button" className="secondary-btn" onClick={signup}>إنشاء حساب</button><button type="button" className="link-btn" onClick={reset}>نسيت كلمة المرور؟</button>{authMsg&&<div className="auth-msg">{authMsg}</div>}</form></div></div>;

  const engine=status?.settings?.runtime_mode?.startsWith('openrouter')?'OpenRouter':'MUS Engine';
  return <div className="chat-app" dir="rtl">
    <div className={`mobile-backdrop ${mobileOpen?'show':''}`} onClick={()=>setMobileOpen(false)}/>
    <aside className={`chat-sidebar ${mobileOpen?'open':''}`}>
      <div className="sidebar-top"><div className="brand-lockup compact"><div className="brand-mark">M</div><div><strong>MUS AI</strong><span>Research Build</span></div></div><button className="icon-btn" onClick={newChat} title="محادثة جديدة"><Icon name="plus"/></button></div>
      <button className="new-chat" onClick={newChat}><Icon name="plus"/><span>محادثة جديدة</span></button>
      <div className="sidebar-label">المحادثات</div>
      <div className="conversation-list">{conversations.length?conversations.map(c=><button key={c.id} className={`conversation-item ${conversation===c.id?'active':''}`} onClick={()=>openConversation(c)}><Icon name="chat" size={16}/><span>{c.title||'محادثة'}</span></button>):<div className="empty-side">لا توجد محادثات بعد</div>}</div>
      <div className="sidebar-footer"><a className="conversation-item admin-link" href="/admin"><Icon name="settings" size={17}/><span>لوحة التحكم</span></a><button className="conversation-item" onClick={()=>sb.auth.signOut()}><Icon name="logout" size={17}/><span>تسجيل الخروج</span></button></div>
    </aside>

    <main className="chat-main">
      <header className="chat-header"><button className="icon-btn mobile-menu" onClick={()=>setMobileOpen(true)}><Icon name="menu"/></button><div className="model-title"><strong>MUS AI</strong><span className={`status-dot ${status?.openrouter_configured?'online':'offline'}`}/><small>{status?.last_model||status?.settings?.openrouter_model||engine}</small></div><a className="admin-pill" href="/admin"><Icon name="settings" size={16}/> التحكم</a></header>
      {notice&&<div className="inline-notice">{notice}</div>}
      <section className={`message-stage ${messages.length?'has-messages':'empty-stage'}`}>
        {!messages.length&&<div className="welcome-state"><div className="welcome-mark">M</div><h1>كيف أستطيع مساعدتك؟</h1><p>MUS AI يستخدم الآن أفضل محرك متاح، بينما نبني نموذجه المستقل وندربه تدريجيًا.</p><div className="prompt-grid"><button onClick={()=>setInput('حلّل لي هذه الفكرة بعمق وحدد نقاط القوة والضعف.')}>حلّل فكرة بعمق</button><button onClick={()=>setInput('ابحث عن أفضل طريقة لحل هذه المشكلة واذكر الأدلة.')}>ابحث وقارن</button><button onClick={()=>setInput('ضع لي خطة عملية مختصرة لتحقيق هذا الهدف.')}>ابنِ خطة عملية</button></div></div>}
        {messages.map((m,i)=><article key={m.id||i} className={`message-row ${m.role}`}><div className="message-avatar">{m.role==='assistant'?'M':'أ'}</div><div className="message-body"><div className="message-name">{m.role==='assistant'?'MUS AI':'أنت'}{m.role==='assistant'&&m.provider&&<span>{m.provider}</span>}</div><div className="message-content">{m.content}</div></div></article>)}
        {busy&&<article className="message-row assistant"><div className="message-avatar">M</div><div className="message-body"><div className="message-name">MUS AI</div><div className="typing"><i/><i/><i/></div></div></article>}
        <div ref={endRef}/>
      </section>
      <footer className="composer-wrap"><div className="composer-box"><textarea rows="1" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder="اكتب رسالتك إلى MUS AI..."/><div className="composer-actions"><button className={`tool-toggle ${webSearch?'active':''}`} onClick={()=>setWebSearch(v=>!v)} title="بحث ويب"><Icon name="globe" size={17}/><span>بحث الويب</span></button><div className="composer-spacer"/><span className="engine-label">{engine}</span><button className="send-btn" onClick={send} disabled={busy||!input.trim()}><Icon name="send" size={17}/></button></div></div><div className="composer-note">قد يخطئ MUS AI. تحقق من المعلومات المهمة.</div></footer>
    </main>
  </div>
}
