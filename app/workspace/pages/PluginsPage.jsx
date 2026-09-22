import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.js';
import Icon from '../components/Icon.jsx';

// Classification: built-in tools ship with the product; the rest are external apps.
const BUILT_IN = { 'web-search': 'globe', 'code-interpreter': 'terminal', 'image-gen': 'image' };
const APP_ICON = { github: 'git', calendar: 'clock', drive: 'folder' };

export default function PluginsPage({ onMenu }) {
  const { t } = useI18n();
  const [plugins, setPlugins] = useState([]);
  const [q, setQ] = useState('');
  const [connecting, setConnecting] = useState(null);
  const [token, setToken] = useState('');
  const [scopes, setScopes] = useState([]);
  const [note, setNote] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.get('/plugins').then(setPlugins).catch(() => {});
  useEffect(() => { load(); }, []);
  const setP = (id, patch) => api.patch('/plugins/' + id, patch).then(load);

  const connect = async () => {
    if (!token.trim()) return;
    setBusy(true);
    try {
      const r = await api.post(`/plugins/${connecting.id}/connect`, { token: token.trim(), scopes });
      setNote({ ok: r.status === 'connected', text: r.note || (r.status === 'connected' ? t('apps.connected') : t('common.error')) });
      if (r.status === 'connected') setTimeout(() => { setConnecting(null); setToken(''); setNote(null); }, 1200);
      load();
    } catch (e) { setNote({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  };

  const match = p => !q || (p.name + ' ' + p.description).toLowerCase().includes(q.toLowerCase());
  const tools = plugins.filter(p => BUILT_IN[p.id] && match(p));
  const apps = plugins.filter(p => !BUILT_IN[p.id] && match(p));

  const descKey = p => 'apps.d.' + p.id;

  return (
    <>
      <div className="topbar">
        <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
        <h1>{t('apps.title')}</h1>
        <input className="input" style={{ maxWidth: 220 }} placeholder={t('apps.search')} value={q} onChange={e => setQ(e.target.value)} />
      </div>
      <div className="content narrow" style={{ maxWidth: 860 }}>
        <div className="card" style={{ marginBottom: 14 }}><b>{t('apps.browserNoticeTitle')}</b><p className="muted small" style={{ margin: '6px 0 0' }}>{t('apps.browserNotice')}</p></div>
        {tools.length > 0 && <>
          <div className="sec-title">{t('apps.builtin')}</div>
          <p className="muted small" style={{ marginTop: -4 }}>{t('apps.builtinHint')}</p>
          <div className="tool-row">
            {tools.map(p => (
              <div key={p.id} className="tool-tile">
                <span className="tic"><Icon name={BUILT_IN[p.id]} size={18} /></span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span className="tname">{t('apps.n.' + p.id)}</span>
                  <span className="tdesc">{t(descKey(p))}</span>
                </span>
                <button className={'switch' + (p.enabled ? ' on' : '')} role="switch" aria-checked={false} disabled title={t('apps.adapterRequired')} />
              </div>
            ))}
          </div>
        </>}

        {apps.length > 0 && <>
          <div className="sec-title" style={{ marginTop: 26 }}>{t('apps.external')}</div>
          <p className="muted small" style={{ marginTop: -4 }}>{t('apps.externalHint')}</p>
          <div className="app-grid">
            {apps.map(p => {
              const st = p.connection.status;
              return (
                <div key={p.id} className="app-card">
                  <div className="row">
                    <span className="tic"><Icon name={APP_ICON[p.id] || 'puzzle'} size={18} /></span>
                    <b style={{ flex: 1 }}>{t('apps.n.' + p.id)}</b>
                    {st === 'connected' ? <span className="tag good">{t('apps.connected')}</span>
                      : st === 'error' ? <span className="tag bad">{t('apps.authError')}</span>
                      : <span className="tag">{t('apps.notConnected')}</span>}
                  </div>
                  <p className="muted small" style={{ margin: '8px 0 10px' }}>{t(descKey(p))}</p>
                  {p.connection.scopes?.length > 0 && (
                    <div className="row" style={{ marginBottom: 10, gap: 4 }}>
                      {p.connection.scopes.map(s => <span key={s} className="tag">{s}</span>)}
                    </div>
                  )}
                  <div className="row">
                    {st !== 'connected'
                      ? <button className="btn sm" disabled title={t('apps.browserNotice')}>{t('apps.adapterRequired')}</button>
                      : <button className="btn sm ghost" onClick={() => api.post(`/plugins/${p.id}/disconnect`).then(load)}>{t('apps.disconnect')}</button>}
                    {st === 'error' && (
                      <button className="btn sm ghost" onClick={() => { setConnecting(p); setScopes(p.connection.scopes || []); setNote(null); setToken(''); }}>{t('apps.reconnect')}</button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>}

        <p className="muted small" style={{ marginTop: 22 }}>{t('apps.serverSide')}</p>
      </div>

      {connecting && (
        <div className="modal-backdrop" onClick={() => setConnecting(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>{t('apps.connect')} {t('apps.n.' + connecting.id)}</h3>
            <div className="field">
              <label className="lbl">{t('apps.token')}</label>
              <input className="input" type="password" value={token} onChange={e => setToken(e.target.value)} autoComplete="off"
                onKeyDown={e => { if (e.key === 'Enter') connect(); }} />
              {connecting.id === 'github' && <div className="hint">{t('apps.githubHint')}</div>}
            </div>
            <div className="field">
              <label className="lbl">{t('apps.permissions')}</label>
              <div className="row" style={{ flexWrap: 'wrap' }}>
                {connecting.availableScopes.map(s => (
                  <button key={s} className={'chip' + (scopes.includes(s) ? ' on' : '')}
                    onClick={() => setScopes(sc => sc.includes(s) ? sc.filter(x => x !== s) : [...sc, s])}>{s}</button>
                ))}
              </div>
            </div>
            {note && <p className={note.ok ? 'good-text' : 'bad-text'}>{note.ok ? '✓ ' : ''}{note.text}</p>}
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button className="btn ghost" onClick={() => setConnecting(null)}>{t('common.cancel')}</button>
              <button className="btn" disabled={busy || !token.trim()} onClick={connect}>{t('apps.connect')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
