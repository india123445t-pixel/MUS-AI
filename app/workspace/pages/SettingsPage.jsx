import React, { useEffect, useState } from 'react';
import { NavLink, Routes, Route, Navigate } from '../router.js';
import { api } from '../api.js';
import { useI18n, LANGS } from '../i18n/index.js';
import Icon from '../components/Icon.jsx';

export default function SettingsPage({ theme, setTheme, density, setDensity, onMenu }) {
  const { t } = useI18n();
  const [s, setS] = useState(null);
  const load = () => api.get('/settings').then(setS).catch(() => {});
  useEffect(() => { load(); }, []);
  const save = patch => api.post('/settings', patch).then(load);

  if (!s) return <div className="content">{t('common.loading')}</div>;

  const SECTIONS = [
    ['general', t('set.general'), 'gear'],
    ['appearance', t('set.appearance'), 'spark'],
    ['language', t('set.language'), 'globe'],
    ['personalization', t('set.personalization'), 'user'],
    ['memory', t('set.memory'), 'library'],
    ['web', t('set.web'), 'search'],
    ['data', t('set.data'), 'file'],
    ['advanced', t('set.advanced'), 'terminal'],
    ['about', t('set.about'), 'chat']
  ];

  return (
    <>
      <div className="topbar">
        <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
        <h1>{t('set.title')}</h1>
      </div>
      <div className="settings-shell">
        <nav className="settings-nav">
          {SECTIONS.map(([id, label, ic]) => (
            <NavLink key={id} to={id} className={({ isActive }) => 'navlink' + (isActive ? ' active' : '')}>
              <Icon name={ic} size={15} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="settings-body">
          <Routes>
            <Route index element={<Navigate to="general" replace />} />
            <Route path="general" element={<General t={t} s={s} save={save} />} />
            <Route path="appearance" element={<Appearance t={t} theme={theme} setTheme={setTheme} density={density} setDensity={setDensity} save={save} />} />
            <Route path="language" element={<Language t={t} save={save} />} />
            <Route path="personalization" element={<Personalization t={t} s={s} save={save} />} />
            <Route path="memory" element={<Memory t={t} />} />
            <Route path="models" element={<Navigate to="../advanced" replace />} />
            <Route path="providers" element={<Navigate to="../advanced" replace />} />
            <Route path="provider" element={<Navigate to="../advanced" replace />} />
            <Route path="web" element={<WebResearch t={t} s={s} save={save} />} />
            <Route path="data" element={<DataControls t={t} />} />
            <Route path="advanced" element={<Advanced t={t} />} />
            <Route path="about" element={<About t={t} />} />
          </Routes>
        </div>
      </div>
    </>
  );
}

function Row({ label, hint, children }) {
  return (
    <div className="set-row">
      <div className="set-lbl">
        <div>{label}</div>
        {hint && <div className="hint">{hint}</div>}
      </div>
      <div className="set-ctl">{children}</div>
    </div>
  );
}

function General({ t, s, save }) {
  return (
    <div className="set-card">
      <h2>{t('set.general')}</h2>
      <Row label={t('set.timezone')}>
        <select className="input" value={s.timezone_default || ''} onChange={e => save({ timezone_default: e.target.value })}>
          <option value="">{Intl.DateTimeFormat().resolvedOptions().timeZone} (auto)</option>
          {['Africa/Casablanca', 'Europe/Paris', 'Europe/London', 'America/New_York', 'Asia/Dubai', 'Asia/Riyadh'].map(z =>
            <option key={z} value={z}>{z}</option>)}
        </select>
      </Row>
      <p className="muted small" style={{ marginTop: 14 }}>{t('set.generalNote')}</p>
    </div>
  );
}

function Appearance({ t, theme, setTheme, density, setDensity, save }) {
  return (
    <div className="set-card">
      <h2>{t('set.appearance')}</h2>
      <Row label={t('set.theme')}>
        <div className="seg">
          <button className={theme === 'dark' ? 'on' : ''} onClick={() => { setTheme('dark'); save({ theme: 'dark' }); }}>{t('set.dark')}</button>
          <button className={theme === 'light' ? 'on' : ''} onClick={() => { setTheme('light'); save({ theme: 'light' }); }}>{t('set.light')}</button>
        </div>
      </Row>
      <Row label={t('set.density')}>
        <div className="seg">
          <button className={density === 'comfortable' ? 'on' : ''} onClick={() => { setDensity('comfortable'); save({ density: 'comfortable' }); }}>{t('set.comfortable')}</button>
          <button className={density === 'compact' ? 'on' : ''} onClick={() => { setDensity('compact'); save({ density: 'compact' }); }}>{t('set.compact')}</button>
        </div>
      </Row>
    </div>
  );
}

function Language({ t, save }) {
  const { lang, setLang } = useI18n();
  return (
    <div className="set-card">
      <h2>{t('set.language')}</h2>
      <Row label={t('set.language')}>
        <div className="seg">
          {LANGS.map(l => (
            <button key={l.id} className={lang === l.id ? 'on' : ''}
              onClick={() => { setLang(l.id); save({ language: l.id }); }}>{l.native}</button>
          ))}
        </div>
      </Row>
      <p className="muted small" style={{ marginTop: 14 }}>{t('set.langNote')}</p>
    </div>
  );
}

function Personalization({ t, s, save }) {
  const [v, setV] = useState(s.personalization || '');
  const [ok, setOk] = useState(false);
  return (
    <div className="set-card">
      <h2>{t('set.personalization')}</h2>
      <p className="muted small">{t('set.customInstructionsHint')}</p>
      <textarea className="input" dir="auto" rows={5} value={v} onChange={e => setV(e.target.value)} />
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn sm" onClick={async () => { await save({ personalization: v }); setOk(true); setTimeout(() => setOk(false), 1500); }}>{t('common.save')}</button>
        {ok && <span className="good-text small">✓ {t('set.savedOk')}</span>}
      </div>
    </div>
  );
}

function Memory({ t }) {
  const [items, setItems] = useState([]);
  const [v, setV] = useState('');
  const load = () => api.get('/memory').then(setItems);
  useEffect(() => { load(); }, []);
  return (
    <div className="set-card">
      <h2>{t('set.memory')}</h2>
      <p className="muted small">{t('set.memoryHint')}</p>
      <div className="row">
        <input className="input" dir="auto" value={v} onChange={e => setV(e.target.value)} placeholder={t('set.addMemory')}
          onKeyDown={e => { if (e.key === 'Enter' && v.trim()) { api.post('/memory', { content: v }).then(() => { setV(''); load(); }); } }} />
        <button className="btn sm" onClick={() => v.trim() && api.post('/memory', { content: v }).then(() => { setV(''); load(); })}>{t('set.add')}</button>
      </div>
      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map(m => (
          <div key={m.id} className="mem-row">
            <span style={{ flex: 1 }} dir="auto">{m.content}</span>
            <button className="iconbtn" title={t('common.delete')} onClick={() => api.del('/memory/' + m.id).then(load)}><Icon name="trash" size={14} /></button>
          </div>
        ))}
        {items.length === 0 && <div className="muted small">{t('set.noMemories')}</div>}
      </div>
    </div>
  );
}

function WebResearch({ t, s, save }) {
  const depth = s.research_depth || 'standard';
  return (
    <div className="set-card">
      <h2>{t('set.web')}</h2>
      <Row label={t('set.searchDefault')}>
        <button className={'switch' + (s.search_default === 'on' ? ' on' : '')} role="switch" aria-checked={s.search_default === 'on'}
          onClick={() => save({ search_default: s.search_default === 'on' ? '' : 'on' })} />
      </Row>
      <Row label={t('set.researchDepth')}>
        <div className="seg">
          {['quick', 'standard', 'thorough'].map(d => (
            <button key={d} className={depth === d ? 'on' : ''} onClick={() => save({ research_depth: d })}>{t('set.depth.' + d)}</button>
          ))}
        </div>
      </Row>
    </div>
  );
}

function DataControls({ t }) {
  return (
    <div className="set-card">
      <h2>{t('set.data')}</h2>
      <Row label={t('set.export')}>
        <button className="btn sm ghost" onClick={() => api.downloadExport()}><Icon name="download" size={14} /> JSON</button>
      </Row>
      <Row label={t('set.clearChats')}>
        <button className="btn sm danger" onClick={async () => {
          const word = t('set.clearConfirmWord');
          const typed = prompt(t('set.clearConfirm', { word }));
          if (typed === word) { await api.post('/data/clear-chats'); window.location.href = '/chat'; }
        }}>{t('common.delete')}</button>
      </Row>
    </div>
  );
}

function Advanced({ t }) {
  const [diag, setDiag] = useState(null);
  return (
    <div className="set-card">
      <h2>{t('set.advanced')}</h2>
      <p className="muted small">{t('set.advancedHint')}</p>
      <Row label={t('set.diagnostics')}>
        <button className="btn sm ghost" onClick={async () => {
          try {
            const b = await api.get('/bootstrap');
            setDiag(JSON.stringify(b, null, 2));
          } catch (e) { setDiag(String(e.message)); }
        }}>{t('set.runDiagnostics')}</button>
      </Row>
      {diag && <pre className="preview-pre" style={{ marginTop: 12, direction: 'ltr', textAlign: 'left' }}>{diag}</pre>}
    </div>
  );
}

function About({ t }) {
  return (
    <div className="set-card">
      <h2>{t('set.about')}</h2>
      <p className="muted">{t('set.aboutText')}</p>
      <p className="muted small">{t('set.aboutVersion')}</p>
    </div>
  );
}
