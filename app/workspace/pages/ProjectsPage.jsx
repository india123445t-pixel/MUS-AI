import React, { useEffect, useState } from 'react';
import { useNavigate } from '../router.js';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.js';
import Icon from '../components/Icon.jsx';

export default function ProjectsPage({ onMenu }) {
  const { t, lang } = useI18n();
  const [projects, setProjects] = useState([]);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: '', instructions: '' });
  const nav = useNavigate();

  const load = () => api.get('/projects').then(setProjects).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name.trim()) return;
    const p = await api.post('/projects', form);
    setShow(false);
    nav('/projects/' + p.id);
  };

  return (
    <>
      <div className="topbar">
        <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
        <h1>{t('proj.title')}</h1>
        <button className="btn" onClick={() => setShow(true)}><Icon name="plus" size={15} /> {t('proj.new')}</button>
      </div>
      <div className="content narrow" style={{ maxWidth: 860 }}>
        {projects.length === 0 && (
          <div className="empty"><Icon name="folder" size={28} /><p>{t('proj.empty')}</p></div>
        )}
        <div className="app-grid">
          {projects.map(p => (
            <button key={p.id} className="app-card click" onClick={() => nav('/projects/' + p.id)} style={{ textAlign: 'start', cursor: 'pointer' }}>
              <div className="row">
                <span className="tic"><Icon name="folder" size={18} /></span>
                <b style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} dir="auto">{p.name}</b>
              </div>
              <div className="muted small" style={{ marginTop: 8 }}>
                {t('proj.counts', { chats: p.chatCount, files: p.fileCount })}
              </div>
              <div className="muted small" style={{ marginTop: 4 }}>
                {new Date(p.created_at).toLocaleDateString(lang === 'ar' ? 'ar' : undefined)}
              </div>
            </button>
          ))}
        </div>
      </div>

      {show && (
        <div className="modal-backdrop" onClick={() => setShow(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>{t('proj.new')}</h3>
            <div className="field">
              <label className="lbl">{t('proj.name')}</label>
              <input className="input" dir="auto" autoFocus value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                onKeyDown={e => { if (e.key === 'Enter') create(); }} />
            </div>
            <div className="field">
              <label className="lbl">{t('proj.instructions')}</label>
              <textarea className="input" dir="auto" rows={4} value={form.instructions}
                onChange={e => setForm({ ...form, instructions: e.target.value })} />
              <div className="hint">{t('proj.instructionsHint')}</div>
            </div>
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button className="btn ghost" onClick={() => setShow(false)}>{t('common.cancel')}</button>
              <button className="btn" disabled={!form.name.trim()} onClick={create}>{t('common.create')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
