import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from '../router.js';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.js';
import Icon from '../components/Icon.jsx';

export default function ProjectDetail({ onChatsChanged, onMenu }) {
  const { id } = useParams();
  const nav = useNavigate();
  const { t, lang } = useI18n();
  const [p, setP] = useState(null);
  const [instr, setInstr] = useState('');
  const [savedTick, setSavedTick] = useState(false);
  const [tab, setTab] = useState('chats');
  const [jobs, setJobs] = useState([]);
  const fileRef = useRef();

  const load = () => api.get('/projects/' + id).then(r => { setP(r); setInstr(r.instructions || ''); }).catch(() => nav('/projects'));
  useEffect(() => {
    load();
    api.get('/jobs').then(all => setJobs(all.filter(j => {
      try { return JSON.parse(j.input || '{}').projectId === id; } catch { return false; }
    }))).catch(() => {});
  }, [id]);

  if (!p) return <div className="content">{t('common.loading')}</div>;

  const newChat = async () => {
    const c = await api.post('/chats', { projectId: id });
    onChatsChanged();
    nav('/chat/' + c.id);
  };

  const upload = async f => {
    const fd = new FormData();
    fd.append('file', f);
    fd.append('projectId', id);
    await api.upload('/files', fd);
    load();
  };

  const saveInstr = async () => {
    await api.patch('/projects/' + id, { instructions: instr });
    setSavedTick(true); setTimeout(() => setSavedTick(false), 1500);
    load();
  };

  const TABS = [
    ['chats', t('proj.tab.chats'), p.chats.length],
    ['files', t('proj.tab.files'), p.files.length],
    ['tasks', t('proj.tab.tasks'), jobs.length],
    ['context', t('proj.tab.context'), null]
  ];

  return (
    <>
      <div className="topbar">
        <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
        <button className="iconbtn" onClick={() => nav('/projects')}><Icon name="chevR" size={16} flip /></button>
        <h1 dir="auto">{p.name}</h1>
        <button className="btn" onClick={newChat}><Icon name="plus" size={15} /> {t('proj.newChat')}</button>
        <button className="iconbtn" title={t('common.delete')} onClick={async () => {
          if (confirm(t('proj.deleteConfirm'))) { await api.del('/projects/' + id); nav('/projects'); }
        }}><Icon name="trash" size={16} /></button>
      </div>
      <div className="content narrow" style={{ maxWidth: 760 }}>
        <div className="seg" style={{ marginBottom: 16 }}>
          {TABS.map(([k, label, n]) => (
            <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>
              {label}{n !== null && n > 0 ? ` (${n})` : ''}
            </button>
          ))}
        </div>

        {tab === 'chats' && (
          <div className="card">
            {p.chats.length === 0 && <div className="muted">{t('proj.noChats')}</div>}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {p.chats.map(c => (
                <button key={c.id} className="recent-item" onClick={() => nav('/chat/' + c.id)}>
                  <Icon name="chat" size={14} />
                  <span className="rtitle" dir="auto">{c.title}</span>
                  <span className="muted small" style={{ flex: 'none' }}>{new Date(c.updated_at).toLocaleDateString(lang === 'ar' ? 'ar' : undefined)}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {tab === 'files' && (
          <div className="card">
            <div className="row" style={{ marginBottom: 8 }}>
              <button className="btn sm ghost" onClick={() => fileRef.current.click()}><Icon name="plus" size={14} /> {t('lib.upload')}</button>
              <input hidden type="file" ref={fileRef} onChange={e => e.target.files[0] && upload(e.target.files[0])} />
            </div>
            {p.files.length === 0 && <div className="muted">{t('proj.noFiles')}</div>}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {p.files.map(f => (
                <a key={f.id} className="recent-item" href={api.fileUrl(f.id)} target="_blank" rel="noreferrer" style={{ textDecoration: 'none', color: 'inherit' }}>
                  <Icon name="file" size={14} />
                  <span className="rtitle" dir="auto">{f.name}</span>
                  <span className="muted small" style={{ flex: 'none' }}>{(f.size / 1024).toFixed(1)} KB</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {tab === 'tasks' && (
          <div className="card">
            {jobs.length === 0 && <div className="muted">{t('proj.noTasks')}</div>}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {jobs.map(j => (
                <button key={j.id} className="recent-item" onClick={() => nav('/work/' + j.id)}>
                  <Icon name="work" size={14} />
                  <span className="rtitle" dir="auto">{j.title}</span>
                  <span className="tag" style={{ flex: 'none' }}>{t('work.' + (['done', 'failed', 'cancelled'].includes(j.status) ? j.status : j.status === 'queued' ? 'queued' : 'running'))}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {tab === 'context' && (
          <div className="card">
            <b>{t('proj.instructions')}</b>
            <p className="muted small">{t('proj.instructionsHint')}</p>
            <textarea className="input" dir="auto" rows={5} value={instr} onChange={e => setInstr(e.target.value)} />
            <div className="row" style={{ marginTop: 10 }}>
              <button className="btn sm" onClick={saveInstr}>{t('common.save')}</button>
              {savedTick && <span className="good-text small">✓ {t('common.saved')}</span>}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
