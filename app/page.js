'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

const CHAT_KEY='aqlevon-ai-public-chats-v3';
const SESSION_KEY='aqlevon-ai-public-session-v2';
const LEGACY_KEYS=['aqlevon-ai-public-chats-v1','aqlevon-ai-public-chats-v2','mus-ai-public-chats-v1','mus-ai-public-chats-v2','aqlevon-ai-public-session-v1'];

function uid(){return globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(36).slice(2)}`}
function Icon({name,size=18}){
  const common={width:size,height:size,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.8,strokeLinecap:'round',strokeLinejoin:'round','aria-hidden':true};
  const paths={plus:<><path d="M12 5v14M5 12h14"/></>,chat:<><path d="M21 15a4 4 0 0 1-4 4H8l-5 3 1.7-5A7 7 0 0 1 3 12V8a5 5 0 0 1 5-5h9a4 4 0 0 1 4 4z"/></>,send:<><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></>,globe:<><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></>,menu:<><path d="M4 7h16M4 12h16M4 17h16"/></>,install:<><path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/></>,thumbUp:<><path d="M7 10v10H3V10h4Zm0 10h9a3 3 0 0 0 3-2.4l1-5A3 3 0 0 0 17 9h-4l1-4a2 2 0 0 0-3.6-1.5L7 10"/></>,thumbDown:<><path d="M7 14V4H3v10h4Zm0-10h9a3 3 0 0 1 3 2.4l1 5A3 3 0 0 1 17 15h-4l1 4a2 2 0 0 1-3.6 1.5L7 14"/></>,trash:<><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13"/></>};
  return <svg {...common}>{paths[name]||paths.chat}</svg>
}
function normalizeChats(raw){try{const a=JSON.parse(raw||'[]');return Array.isArray(a)?a.filter(x=>x?.id&&Array.isArray(x.messages)).slice(0,30):[]}catch{return []}}

export default function ChatPage(){
  const [ready,setReady]=useState(false),[status,setStatus]=useState(null),[sessionId,setSessionId]=useState(''),[chats,setChats]=useState([]),[activeId,setActiveId]=useState(null),[input,setInput]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[webSearch,setWebSearch]=useState(false),[mobileOpen,setMobileOpen]=useState(false),[installPrompt,setInstallPrompt]=useState(null),[standalone,setStandalone]=useState(false);
  const endRef=useRef(null);
  const active=useMemo(()=>chats.find(c=>c.id===activeId)||null,[chats,activeId]);
  const messages=active?.messages||[];

  useEffect(()=>{
    for(const key of LEGACY_KEYS)localStorage.removeItem(key);
    const sid=localStorage.getItem(SESSION_KEY)||uid();localStorage.setItem(SESSION_KEY,sid);setSessionId(sid);
    const stored=normalizeChats(localStorage.getItem(CHAT_KEY));setChats(stored);setActiveId(stored[0]?.id||null);
    setStandalone(window.matchMedia?.('(display-mode: standalone)')?.matches||window.navigator.standalone===true);
    loadStatus();
    if('serviceWorker'in navigator)navigator.serviceWorker.register('/api/status?sw=1',{scope:'/'}).catch(()=>{});
    const before=e=>{e.preventDefault();setInstallPrompt(e)};const installed=()=>{setStandalone(true);setInstallPrompt(null)};
    window.addEventListener('beforeinstallprompt',before);window.addEventListener('appinstalled',installed);setReady(true);
    return()=>{window.removeEventListener('beforeinstallprompt',before);window.removeEventListener('appinstalled',installed)};
  },[]);
  useEffect(()=>{if(ready)localStorage.setItem(CHAT_KEY,JSON.stringify(chats.slice(0,30)))},[chats,ready]);
  useEffect(()=>{endRef.current?.scrollIntoView({behavior:'smooth'})},[messages,busy]);

  async function loadStatus(){try{const r=await fetch('/api/status',{cache:'no-store'});if(r.ok){const d=await r.json();setStatus(d);setWebSearch(!!d?.settings?.web_search_default&&!!d?.settings?.public_web_search_enabled)}}catch{}}
  function newChat(){setActiveId(null);setInput('');setNotice('');setMobileOpen(false)}
  function removeChat(id){setChats(v=>v.filter(c=>c.id!==id));if(activeId===id)setActiveId(null)}
  function patchChat(id,updater){setChats(prev=>prev.map(c=>c.id===id?updater(c):c).sort((a,b)=>b.updatedAt-a.updatedAt))}
  function openChat(id){setActiveId(id);setMobileOpen(false);setNotice('')}

  async function send(){
    const text=input.trim();if(!text||busy||status?.settings?.public_chat_enabled===false)return;
    setNotice('');setInput('');setBusy(true);
    const cid=activeId||uid();const previous=activeId?(active?.messages||[]):[];const userMsg={id:uid(),role:'user',content:text};
    if(!activeId){setChats(v=>[{id:cid,title:text.slice(0,58),messages:[userMsg],updatedAt:Date.now()},...v]);setActiveId(cid)}else patchChat(cid,c=>({...c,messages:[...c.messages,userMsg],updatedAt:Date.now()}));
    try{
      const history=previous.slice(-20).map(({role,content})=>({role,content}));
      const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:text,history,webSearch,sessionId,conversationId:cid})});
      const d=await r.json();if(!r.ok)throw Error(d.message||'تعذر الوصول إلى AQLEVON AI.');
      const assistant={id:uid(),role:'assistant',content:d.text,chatLogId:d.chat_log_id||null,feedback:null};
      patchChat(cid,c=>({...c,messages:[...c.messages,assistant],updatedAt:Date.now()}));
    }catch(e){setNotice(e.message)}finally{setBusy(false)}
  }
  async function rate(message,rating){if(!message?.chatLogId||!sessionId)return;try{const r=await fetch('/api/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'feedback',chatLogId:message.chatLogId,sessionId,rating})});if(!r.ok)return;patchChat(activeId,c=>({...c,messages:c.messages.map(m=>m.id===message.id?{...m,feedback:rating}:m),updatedAt:Date.now()}))}catch{}}
  async function install(){if(standalone)return;if(installPrompt){installPrompt.prompt();await installPrompt.userChoice;setInstallPrompt(null);return}setNotice('على الهاتف: افتح قائمة المتصفح ثم اختر «تثبيت التطبيق» أو «إضافة إلى الشاشة الرئيسية».')}

  if(!ready)return <div className="center-screen"><div className="brand-loader"><img src="/logo.svg" alt=""/><b>AQLEVON AI</b></div></div>;
  if(status?.settings?.public_chat_enabled===false)return <div className="center-screen"><div className="maintenance-card"><img src="/logo.svg" alt="AQLEVON AI"/><h1>AQLEVON AI</h1><p>النظام في وضع صيانة مؤقتًا. عد لاحقًا.</p></div></div>;

  return <div className="chat-app public-app" dir="rtl">
    <div className={`mobile-backdrop ${mobileOpen?'show':''}`} onClick={()=>setMobileOpen(false)}/>
    <aside className={`chat-sidebar ${mobileOpen?'open':''}`}>
      <div className="sidebar-top"><div className="brand-lockup compact"><img className="brand-icon" src="/logo.svg" alt="AQLEVON AI"/><div><strong>AQLEVON AI</strong><span>A SMARTER TOMORROW</span></div></div><button className="icon-btn" onClick={newChat} title="محادثة جديدة"><Icon name="plus"/></button></div>
      <button className="new-chat" onClick={newChat}><Icon name="plus"/><span>محادثة جديدة</span></button>
      <div className="sidebar-label">محادثاتك على هذا الجهاز</div>
      <div className="conversation-list">{chats.length?chats.map(c=><div key={c.id} className={`conversation-wrap ${activeId===c.id?'active':''}`}><button className="conversation-item" onClick={()=>openChat(c.id)}><Icon name="chat" size={16}/><span>{c.title||'محادثة'}</span></button><button className="delete-chat" onClick={()=>removeChat(c.id)} aria-label="حذف"><Icon name="trash" size={15}/></button></div>):<div className="empty-side">ابدأ أول محادثة مع AQLEVON AI</div>}</div>
      <div className="sidebar-footer">{status?.settings?.install_enabled!==false&&!standalone&&<button className="install-side" onClick={install}><Icon name="install" size={17}/><span>تثبيت AQLEVON AI</span></button>}<div className="privacy-mini">المحادثات مجهولة الهوية وقد تُستخدم لتحسين AQLEVON AI. لا تشارك معلومات حساسة.</div></div>
    </aside>

    <main className="chat-main">
      <header className="chat-header"><button className="icon-btn mobile-menu" onClick={()=>setMobileOpen(true)}><Icon name="menu"/></button><div className="model-title"><img className="header-icon" src="/icon.svg" alt=""/><div><strong>AQLEVON AI</strong><small>Learn · Create · Evolve</small></div><span className={`status-dot ${status?.openrouter_configured||status?.self_hosted_configured?'online':'offline'}`}/></div>{status?.settings?.install_enabled!==false&&!standalone&&<button className="install-pill" onClick={install}><Icon name="install" size={16}/><span>تثبيت</span></button>}</header>
      {notice&&<div className="inline-notice">{notice}</div>}
      <section className={`message-stage ${messages.length?'has-messages':'empty-stage'}`}>
        {!messages.length&&<div className="welcome-state"><img className="welcome-logo" src="/logo.svg" alt="AQLEVON AI"/><h1>كيف أستطيع مساعدتك؟</h1><p>محادثة مباشرة مع AQLEVON AI. لا تحتاج إلى حساب.</p><div className="prompt-grid"><button onClick={()=>setInput('حلّل لي هذه الفكرة بعمق وحدد نقاط القوة والضعف.')}>حلّل فكرة بعمق</button><button onClick={()=>setInput('قارن بين أفضل الحلول لهذه المشكلة واختر الأنسب مع السبب.')}>قارن واختر الأفضل</button><button onClick={()=>setInput('ضع لي خطة عملية واضحة لتحقيق هذا الهدف بأقل تكلفة.')}>ابنِ خطة عملية</button></div></div>}
        {messages.map((m,i)=><article key={m.id||i} className={`message-row ${m.role}`}><div className="message-avatar">{m.role==='assistant'?<img src="/icon.svg" alt=""/>:'أ'}</div><div className="message-body"><div className="message-name">{m.role==='assistant'?'AQLEVON AI':'أنت'}</div><div className="message-content">{m.content}</div>{m.role==='assistant'&&m.chatLogId&&<div className="message-tools"><button className={m.feedback==='good'?'selected':''} onClick={()=>rate(m,'good')} title="إجابة جيدة"><Icon name="thumbUp" size={16}/></button><button className={m.feedback==='bad'?'selected':''} onClick={()=>rate(m,'bad')} title="إجابة ضعيفة"><Icon name="thumbDown" size={16}/></button></div>}</div></article>)}
        {busy&&<article className="message-row assistant"><div className="message-avatar"><img src="/icon.svg" alt=""/></div><div className="message-body"><div className="message-name">AQLEVON AI</div><div className="typing"><i/><i/><i/></div></div></article>}
        <div ref={endRef}/>
      </section>
      <footer className="composer-wrap"><div className="composer-box"><textarea rows="1" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder="اسأل AQLEVON AI..."/><div className="composer-actions">{status?.settings?.public_web_search_enabled&&<button className={`tool-toggle ${webSearch?'active':''}`} onClick={()=>setWebSearch(v=>!v)} title="بحث ويب"><Icon name="globe" size={17}/><span>بحث الويب</span></button>}<div className="composer-spacer"/><button className="send-btn" onClick={send} disabled={busy||!input.trim()}><Icon name="send" size={17}/></button></div></div><div className="composer-note">قد تُستخدم المحادثات المجهولة لتحسين AQLEVON AI. لا ترسل أسرارًا أو بيانات شخصية حساسة.</div></footer>
    </main>
  </div>
}
