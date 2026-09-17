import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from '../router.js';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.js';
import Icon from '../components/Icon.jsx';
import Markdown from '../components/Markdown.jsx';

function daypartKey() {
  const h = new Date().getHours();
  return h < 12 ? 'chat.morning' : h < 18 ? 'chat.afternoon' : 'chat.evening';
}

export default function ChatPage({ onChatsChanged, newChat, onMenu }) {
  const { id } = useParams();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const { t } = useI18n();
  const [chat, setChat] = useState(null);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [thinkLonger, setThinkLonger] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  const [deepResearch, setDeepResearch] = useState(false);
  const [editing, setEditing] = useState(null);
  const [listening, setListening] = useState(false);
  const [addMenu, setAddMenu] = useState(false);
  const [codeSheet, setCodeSheet] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [titleEdit, setTitleEdit] = useState(null);
  const scrollRef = useRef();
  const fileRef = useRef();
  const imgRef = useRef();
  const taRef = useRef();
  const recRef = useRef(null);
  const abortRef = useRef(null);
  const busyRef = useRef(false);
  const streamChatIdRef = useRef(null);

  const isTemp = params.get('temp') === '1' || chat?.temporary === 1;

  useEffect(() => {
    setEditing(null); setLastError(null); setTitleEdit(null);
    if (!id) { setChat(null); return; }
    // Mid-send navigation (first message of a new chat replaces /chat with
    // /chat/:id): the in-flight optimistic state is already correct; a refetch
    // here would clobber the streaming bubble and hide live deltas + Stop.
    if (busyRef.current) return;
    api.get('/chats/' + id).then(setChat).catch(() => nav('/chat'));
  }, [id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [chat?.messages?.length, busy]);

  const autoGrow = () => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  };

  const send = async (text, extra = {}) => {
    const content = (text ?? input).trim();
    if (!content && !extra.regenerate && !extra.editMessageId) return;
    setBusy(true); busyRef.current = true;
    setInput(''); setEditing(null); setLastError(null);
    if (taRef.current) taRef.current.style.height = 'auto';

    let chatId = id;
    if (!chatId) {
      const c = await api.post('/chats', { temporary: false });
      chatId = c.id;
      nav('/chat/' + chatId, { replace: true });
    }
    if (content && !extra.editMessageId) {
      setChat(prev => prev ? { ...prev, messages: [...(prev.messages || []), { id: 'tmp-u', role: 'user', content }] } : { id: chatId, title: '', messages: [{ id: 'tmp-u', role: 'user', content }] });
    }
    setChat(prev => prev ? { ...prev, messages: [...(prev.messages || []), { id: 'tmp-a', role: 'assistant', content: '', streaming: true }] } : prev);

    const controller = new AbortController();
    abortRef.current = controller;
    streamChatIdRef.current = chatId;
    try {
      const resp = await api.streamChat(chatId, {
        content: content || undefined,
        reasoning: thinkLonger ? 'extended' : 'standard',
        useWebSearch: webSearch || deepResearch,
        ...extra
      }, controller.signal);
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = '', acc = '', sources = null, hadError = null;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const frames = buf.split('\n\n'); buf = frames.pop();
        for (const f of frames) {
          const ev = (f.match(/^event: (.+)$/m) || [])[1];
          const dataRaw = (f.match(/^data: (.+)$/m) || [])[1];
          if (!ev || !dataRaw) continue;
          const data = JSON.parse(dataRaw);
          if (ev === 'delta') {
            acc += data.t;
            setChat(prev => ({ ...prev, messages: prev.messages.map(mm => mm.id === 'tmp-a' ? { ...mm, content: acc } : mm) }));
          } else if (ev === 'sources') {
            sources = data.sources;
          } else if (ev === 'done') {
            if (data.error) hadError = data.error;
            const fresh = await api.get('/chats/' + chatId);
            if (sources) fresh.sources = sources;
            setChat(fresh);
            onChatsChanged();
          }
        }
      }
      if (hadError) setLastError(hadError);
    } catch (e) {
      if (e.name === 'AbortError') {
        // Deterministic stop path: stop() asks the SERVER to abort (see below)
        // and the stream stays open until the server has persisted the partial
        // and sent its final `done` event — handled above, so we normally never
        // land here on Stop. This branch only fires if the fetch itself was
        // aborted (e.g. component unmount / connection torn down); refetch
        // best-effort so nothing visible is lost.
        try { const fresh = await api.get('/chats/' + chatId); setChat(fresh); onChatsChanged(); } catch { /* offline */ }
      } else {
        setLastError(e.message);
        try { const fresh = await api.get('/chats/' + chatId); setChat(fresh); } catch { /* offline */ }
      }
    } finally {
      abortRef.current = null;
      streamChatIdRef.current = null;
      busyRef.current = false;
      setBusy(false);
    }
  };

  // Deterministic Stop: tell the server to abort generation, then KEEP READING
  // the open stream. The server persists the partial reply first and only then
  // emits the final `done` event, which triggers the normal refetch above — the
  // stopped partial is guaranteed to be in that refetch (no timing assumptions).
  // Client-side fetch abort is only a fallback if the stop request itself fails.
  const stop = () => {
    const chatId = streamChatIdRef.current;
    if (!chatId) { abortRef.current?.abort(); return; }
    api.post(`/chats/${chatId}/stream/stop`, {}).catch(() => abortRef.current?.abort());
  };
  const regenerate = () => send('', { regenerate: true });
  const saveEdit = (msgId, newText) => send(newText, { editMessageId: msgId });

  const branch = async (msgId) => {
    const r = await api.post(`/chats/${id}/branch`, { messageId: msgId });
    onChatsChanged();
    nav('/chat/' + r.id);
  };

  const readAloud = (text) => {
    speechSynthesis.cancel();
    speechSynthesis.speak(new SpeechSynthesisUtterance(text.replace(/[#*`>|]/g, '')));
  };

  const dictate = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    if (listening) { recRef.current?.stop(); return; }
    const rec = new SR();
    recRef.current = rec;
    rec.interimResults = true; rec.continuous = true;
    rec.onresult = e => setInput(Array.from(e.results).map(r => r[0].transcript).join(''));
    rec.onend = () => setListening(false);
    rec.start(); setListening(true);
  };

  const uploadFile = async (f, thenSummarize = false) => {
    const fd = new FormData();
    fd.append('file', f);
    const file = await api.upload('/files', fd);
    if (thenSummarize) {
      send(`${t('chat.starter.summarize')}: [${t('chat.attached')}: ${file.name}]`);
    } else {
      setInput(v => v + (v ? '\n' : '') + `[${t('chat.attached')}: ${file.name}]`);
      taRef.current?.focus();
    }
  };

  const saveTitle = async () => {
    const v = (titleEdit || '').trim();
    setTitleEdit(null);
    if (v && v !== chat?.title) {
      await api.patch('/chats/' + id, { title: v });
      setChat(prev => ({ ...prev, title: v }));
      onChatsChanged();
    }
  };

  const delChat = async () => {
    if (!confirm(t('confirm.deleteChat'))) return;
    await api.del('/chats/' + id);
    onChatsChanged(); nav('/chat');
  };

  // Contextual starters (spec §2)
  const starters = [
    { key: 'summarize', icon: 'file', run: () => fileRef.current?.click() && undefined, mode: 'file' },
    { key: 'plan', icon: 'work', run: () => { setInput(t('chat.planTemplate')); taRef.current?.focus(); setTimeout(autoGrow, 0); } },
    { key: 'code', icon: 'code', run: () => setCodeSheet(true) },
    { key: 'email', icon: 'pencil', run: () => { setInput(t('chat.emailTemplate')); taRef.current?.focus(); setTimeout(autoGrow, 0); } }
  ];
  const summarizeRef = useRef(false);

  const messages = chat?.messages || [];

  return (
    <>
      <div className="topbar">
        <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
        {id && titleEdit !== null ? (
          <input className="title-edit" autoFocus value={titleEdit}
            onChange={e => setTitleEdit(e.target.value)}
            onBlur={saveTitle}
            onKeyDown={e => { if (e.key === 'Enter') saveTitle(); if (e.key === 'Escape') setTitleEdit(null); }} />
        ) : (
          <h1 onDoubleClick={() => id && setTitleEdit(chat?.title || '')}>{chat?.title || t('app.chats')}</h1>
        )}
        {isTemp && <span className="tag warn">{t('chat.temporary')}</span>}
        {id && (
          <>
            <button className="iconbtn" title={t('menu.rename')} onClick={() => setTitleEdit(chat?.title || '')}><Icon name="pencil" size={16} /></button>
            <button className="iconbtn" title={t('menu.delete')} onClick={delChat}><Icon name="trash" size={16} /></button>
          </>
        )}
        <button className="chip" onClick={() => newChat(true)}>{t('chat.temporaryChat')}</button>
      </div>

      {!id || messages.length === 0 ? (
        <div className="empty-hero">
          <div className="inner">
            <h2>{t(daypartKey())}</h2>
            <p className="sub">{t('chat.hint')}</p>
            <div className="starters">
              {starters.map(s => (
                <button key={s.key} className="starter" onClick={() => {
                  if (s.mode === 'file') { summarizeRef.current = true; fileRef.current?.click(); }
                  else s.run();
                }}>
                  <span className="st"><Icon name={s.icon} size={16} /> {t('chat.starter.' + s.key)}</span>
                  <span className="sd">{t('chat.starter.' + s.key + '.d')}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-inner">
            {messages.map((m, i) => (
              <div key={m.id + i} className={'msg ' + m.role}>
                <div className="role">{m.role === 'user' ? t('chat.you') : t('chat.assistant')}</div>
                {editing === m.id ? (
                  <EditBox initial={m.content} t={t} onCancel={() => setEditing(null)} onSave={v => saveEdit(m.id, v)} />
                ) : (
                  <div className="bubble" dir="auto">
                    {m.role === 'assistant' ? <Markdown text={m.content} /> : m.content}
                    {m.streaming && <span className="stream-caret" />}
                  </div>
                )}
                {m.role === 'assistant' && chat.sources && i === messages.length - 1 && (
                  <div className="sources-row">
                    {chat.sources.map((s, n) => (
                      <a key={n} className="src-chip" href={s.url} target="_blank" rel="noreferrer">
                        <span className="n">{n + 1}</span> {s.title || new URL(s.url).hostname}
                      </a>
                    ))}
                  </div>
                )}
                {!m.streaming && (
                  <div className="msg-actions">
                    <button className="iconbtn" title={t('chat.copy')} onClick={() => navigator.clipboard.writeText(m.content)}><Icon name="copy" size={15} /></button>
                    {m.role === 'user' && <button className="iconbtn" title={t('chat.edit')} onClick={() => setEditing(m.id)}><Icon name="pencil" size={15} /></button>}
                    {m.role === 'assistant' && <>
                      <button className="iconbtn" title={t('chat.readAloud')} onClick={() => readAloud(m.content)}><Icon name="volume" size={15} /></button>
                      <button className="iconbtn" title={t('chat.good')}><Icon name="thumbUp" size={15} /></button>
                      <button className="iconbtn" title={t('chat.bad')}><Icon name="thumbDown" size={15} /></button>
                      {i === messages.length - 1 && <button className="iconbtn" title={t('chat.retry')} onClick={regenerate} disabled={busy}><Icon name="retry" size={15} /> {t('chat.retry')}</button>}
                    </>}
                    <button className="iconbtn" title={t('chat.branch')} onClick={() => branch(m.id)}><Icon name="branch" size={15} /></button>
                  </div>
                )}
              </div>
            ))}
            {lastError && (
              <div className="error-strip">
                <Icon name="warn" size={16} />
                <span style={{ flex: 1 }}>{t('chat.errorStrip')}</span>
                <button className="btn sm ghost" onClick={regenerate}>{t('chat.retry')}</button>
              </div>
            )}
            {busy && !messages.some(m => m.id === 'tmp-a') && (
              <div className="msg assistant"><div className="role">{t('chat.assistant')}</div><span className="typing"><i /><i /><i /></span></div>
            )}
          </div>
        </div>
      )}

      <div className="composer-wrap">
        <div className="composer">
          <textarea
            ref={taRef}
            dir="auto"
            placeholder={listening ? t('chat.listening') : t('chat.placeholder')}
            value={input}
            onChange={e => { setInput(e.target.value); autoGrow(); }}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
            rows={1}
          />
          <div className="composer-row">
            <div style={{ position: 'relative' }}>
              <button className="chip" onClick={() => setAddMenu(v => !v)} aria-label={t('chat.add')}>
                <Icon name="plus" size={15} /><span className="chip-label">{t('chat.add')}</span>
              </button>
              {addMenu && <>
                <div className="menu-backdrop" onClick={() => setAddMenu(false)} />
                <div className="menu" style={{ bottom: 40, insetInlineStart: 0 }}>
                  <button onClick={() => { setAddMenu(false); fileRef.current?.click(); }}><Icon name="clip" size={15} /> {t('chat.attachFile')}</button>
                  <button onClick={() => { setAddMenu(false); imgRef.current?.click(); }}><Icon name="image" size={15} /> {t('chat.addImage')}</button>
                  <button onClick={() => { setAddMenu(false); setCodeSheet(true); }}><Icon name="code" size={15} /> {t('chat.pasteCode')}</button>
                </div>
              </>}
            </div>
            <input type="file" hidden ref={fileRef} onChange={e => {
              const f = e.target.files[0]; e.target.value = '';
              if (f) { const s = summarizeRef.current; summarizeRef.current = false; uploadFile(f, s); }
            }} />
            <input type="file" accept="image/*" hidden ref={imgRef} onChange={e => { const f = e.target.files[0]; e.target.value = ''; if (f) uploadFile(f); }} />

            <button className={'chip' + (webSearch ? ' on' : '')} onClick={() => setWebSearch(v => !v)}>
              <Icon name="globe" size={15} /><span className="chip-label">{t('chat.webSearch')}</span>
            </button>
            <button className={'chip' + (deepResearch ? ' on' : '')} title={t('chat.researchHint')} onClick={() => setDeepResearch(v => !v)}>
              <Icon name="flask" size={15} /><span className="chip-label">{t('chat.deepResearch')}</span>
            </button>

            <div className="spacer" />

            <button
              className={'chip' + (thinkLonger ? ' on' : '')}
              aria-pressed={thinkLonger}
              title={t('chat.thinkLongerHint')}
              onClick={() => setThinkLonger(v => !v)}
            >
              <Icon name="spark" size={14} /><span className="chip-label">{t('chat.thinkLonger')}</span>
            </button>

            <button className={'iconbtn' + (listening ? ' on' : '')} title={t('chat.dictate')} onClick={dictate} style={listening ? { color: 'var(--bad)' } : undefined}>
              <Icon name="mic" size={17} />
            </button>
            {busy
              ? <button className="send-btn stop" onClick={stop} title={t('chat.stop')}><Icon name="stop" size={15} /></button>
              : <button className="send-btn" onClick={() => send()} disabled={!input.trim()} title={t('chat.send')}><Icon name="send" size={16} flip /></button>}
          </div>
        </div>
      </div>

      {codeSheet && (
        <CodeSheet t={t} onClose={() => setCodeSheet(false)} onSubmit={code => {
          setCodeSheet(false);
          send(t('chat.starter.code') + ':\n\n```\n' + code + '\n```');
        }} />
      )}
    </>
  );
}

function EditBox({ initial, onSave, onCancel, t }) {
  const [v, setV] = useState(initial);
  return (
    <div className="card" style={{ padding: 12 }}>
      <textarea className="input" rows={3} value={v} onChange={e => setV(e.target.value)} dir="auto" />
      <div className="row" style={{ marginTop: 8 }}>
        <button className="btn sm" onClick={() => onSave(v)}>{t('chat.saveResend')}</button>
        <button className="btn sm ghost" onClick={onCancel}>{t('chat.cancel')}</button>
      </div>
    </div>
  );
}

function CodeSheet({ onSubmit, onClose, t }) {
  const [code, setCode] = useState('');
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal wide" onClick={e => e.stopPropagation()}>
        <div className="row spread">
          <h3 style={{ margin: 0 }}>{t('chat.codeSheetTitle')}</h3>
          <button className="iconbtn" title={t('common.close')} onClick={onClose}><Icon name="x" size={16} /></button>
        </div>
        <textarea className="input" rows={10} style={{ fontFamily: 'var(--mono)', marginTop: 12, direction: 'ltr', textAlign: 'left' }}
          autoFocus value={code} onChange={e => setCode(e.target.value)} />
        <div className="row" style={{ marginTop: 12, justifyContent: 'flex-end' }}>
          <button className="btn" disabled={!code.trim()} onClick={() => onSubmit(code)}>{t('chat.send')}</button>
        </div>
      </div>
    </div>
  );
}
