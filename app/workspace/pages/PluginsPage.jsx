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
  const [runtime,setRuntime]=useState(null);
  const [settings,setSettings]=useState(null);

  const load = () => Promise.all([api.get('/plugins'),api.get('/bootstrap'),api.get('/settings')]).then(([p,b,s])=>{setPlugins(p);setRuntime(b);setSettings(s)}).catch(() => {});
  useEffect(() => { load(); }, []);
  const toggleWebDefault=async()=>{if(runtime?.webSearchAvailable!==true||!settings)return;await api.post('/settings',{search_default:settings.search_default==='on'?'':'on'});load()};
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
                {p.id==='web-search' ? (
                  <button className={'switch' + (settings?.search_default==='on' ? ' on' : '')} role="switch" aria-checked={settings?.search_default==='on'} disabled={runtime?.webSearchAvailable!==true} title={runtime?.webSearchAvailable===true?undefined:t('apps.adapterRequired')} onClick={toggleWebDefault} />
                ) : (
                  <span className="tag warn">{t('apps.adapterRequired')}</span>
                )}
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
                    <span className="tag warn">{t('apps.adapterRequired')}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </>}

        <p className="muted small" style={{ marginTop: 22 }}>{t('apps.serverSide')}</p>
      </div>

    </>
  );
}
