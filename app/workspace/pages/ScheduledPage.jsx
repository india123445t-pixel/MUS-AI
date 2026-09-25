import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.js';
import Icon from '../components/Icon.jsx';

function humanSchedule(s, t, lang) {
  if (s.kind === 'once') {
    return s.next_run ? t('auto.onceAt') + ' ' + new Date(s.next_run).toLocaleString(lang === 'ar' ? 'ar' : undefined) : t('auto.once');
  }
  if (s.kind === 'monitor') return t('auto.monitor') + (s.condition_query ? ' — ' + s.condition_query : '');
  const m = s.interval_minutes || 60;
  const txt = m % 1440 === 0 ? (m / 1440) + ' d' : m % 60 === 0 ? (m / 60) + ' h' : m + ' ' + t('auto.minutes');
  return t('auto.every') + ' ' + txt;
}

function rel(ts, lang) {
  if (!ts) return '—';
  const d = new Date(ts).getTime() - Date.now();
  const abs = Math.abs(d);
  const fmt = new Intl.RelativeTimeFormat(lang === 'ar' ? 'ar' : 'en', { numeric: 'auto' });
  if (abs < 3600000) return fmt.format(Math.round(d / 60000), 'minute');
  if (abs < 86400000) return fmt.format(Math.round(d / 3600000), 'hour');
  return fmt.format(Math.round(d / 86400000), 'day');
}

// Light natural-language parse: "every 2 hours", "every day at 9", "once tomorrow 14:00"
function parseNatural(text) {
  const s = text.toLowerCase();
  let m;
  if ((m = s.match(/every\s+(\d+)\s*(minute|hour|day)/)) || (m = s.match(/كل\s+(\d+)\s*(دقيقة|ساعة|يوم)/))) {
    const n = Number(m[1]);
    const unit = m[2];
    const mins = /hour|ساعة/.test(unit) ? n * 60 : /day|يوم/.test(unit) ? n * 1440 : n;
    return { kind: 'recurring', intervalMinutes: Math.max(1, mins) };
  }
  if (/every day|daily|يوميا|كل يوم/.test(s)) return { kind: 'recurring', intervalMinutes: 1440 };
  if (/every hour|hourly|كل ساعة/.test(s)) return { kind: 'recurring', intervalMinutes: 60 };
  return null;
}

export default function ScheduledPage({ onMenu }) {
  const { t, lang } = useI18n();
  const [items, setItems] = useState([]);
  const [show, setShow] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [natural, setNatural] = useState('');
  const [form, setForm] = useState({ title: '', kind: 'once', prompt: '', runAt: '', intervalMinutes: 60, conditionQuery: '' });

  const KINDS = [
    { id: 'once', label: t('auto.once') },
    { id: 'recurring', label: t('auto.recurring') },
    { id: 'monitor', label: t('auto.monitor') }
  ];

  const load = () => api.get('/scheduled').then(setItems).catch(() => {});
  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  const applyNatural = v => {
    setNatural(v);
    const parsed = parseNatural(v);
    if (parsed) setForm(f => ({ ...f, ...parsed }));
  };

  const create = async () => {
    if (!form.title.trim()) return;
    try {
      await api.post('/scheduled', form);
      setShow(false); setNatural('');
      setForm({ title: '', kind: 'once', prompt: '', runAt: '', intervalMinutes: 60, conditionQuery: '' });
      load();
    } catch (e) { alert(e.message); }
  };

  const del = async s => {
    if (!confirm(t('auto.deleteConfirm'))) return;
    await api.del('/scheduled/' + s.id); load();
  };

  return (
    <>
      <div className="topbar">
        <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
        <h1>{t('auto.title')}</h1>
        <span className="tag warn">{t('auto.adapterRequired')}</span>
        <button className="btn" onClick={() => setShow(true)}><Icon name="plus" size={15} /> {t('auto.new')}</button>
      </div>
      <div className="content narrow" style={{ maxWidth: 760, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="card"><b>{t('auto.adapterRequired')}</b><p className="muted small" style={{ margin: '6px 0 0' }}>{t('auto.localDraftNotice')}</p></div>
        {items.length === 0 && (
          <div className="empty"><Icon name="clock" size={28} /><p>{t('auto.empty')}</p></div>
        )}
        {items.map(s => {
          const lastRun = (s.runs || [])[0];
          return (
            <div className="card auto-card" key={s.id}>
              <div className="arow">
                <span className={'dot ' + (s.enabled ? (lastRun?.status === 'error' ? 'bad' : 'good') : 'idle')} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="aname" dir="auto">{s.title}</div>
                  <div className="asched">
                    {humanSchedule(s, t, lang)}
                    {s.enabled && s.next_run ? ' · ' + t('auto.nextRun') + ' ' + rel(s.next_run, lang) : ''}
                    {!s.enabled ? ' · ' + t('auto.paused') : ''}
                  </div>
                </div>
                <button className={'switch' + (s.enabled ? ' on' : '')} role="switch" aria-checked={false} disabled title={t('auto.adapterRequired')} />
                <button className="iconbtn" title={t('auto.history')} onClick={() => setExpanded(expanded === s.id ? null : s.id)}><Icon name="history" size={15} /></button>
                <button className="iconbtn" title={t('common.delete')} onClick={() => del(s)}><Icon name="trash" size={15} /></button>
              </div>
              {expanded === s.id && (
                <div style={{ marginTop: 10, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                  {(s.runs || []).length === 0 && <div className="muted small">—</div>}
                  {(s.runs || []).slice(0, 5).map((r, i) => (
                    <div key={i} className="run-row">
                      <span className={'dot ' + (r.status === 'ok' ? 'good' : 'bad')} />
                      <span>{new Date(r.started_at).toLocaleString(lang === 'ar' ? 'ar' : undefined)}</span>
                      <span className="muted">{r.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {show && (
        <div className="modal-backdrop" onClick={() => setShow(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>{t('auto.new')}</h3>
            <div className="field">
              <label className="lbl">{t('auto.name')}</label>
              <input className="input" dir="auto" autoFocus value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="field">
              <label className="lbl">{t('auto.what')}</label>
              <textarea className="input" dir="auto" rows={2} value={form.prompt} onChange={e => setForm({ ...form, prompt: e.target.value })} />
            </div>
            <div className="field">
              <label className="lbl">{t('auto.when')}</label>
              <input className="input" dir="auto" placeholder="every 2 hours / كل ساعة …" value={natural} onChange={e => applyNatural(e.target.value)} />
              <div className="row" style={{ marginTop: 8 }}>
                {KINDS.map(k => (
                  <button key={k.id} className={'chip' + (form.kind === k.id ? ' on' : '')} onClick={() => setForm({ ...form, kind: k.id })}>{k.label}</button>
                ))}
              </div>
            </div>
            {form.kind === 'once' && (
              <div className="field">
                <label className="lbl">{t('auto.onceAt')}</label>
                <input className="input" type="datetime-local" value={form.runAt} onChange={e => setForm({ ...form, runAt: e.target.value })} />
              </div>
            )}
            {form.kind !== 'once' && (
              <div className="field">
                <label className="lbl">{t('auto.every')} ({t('auto.minutes')})</label>
                <input className="input" type="number" min="1" value={form.intervalMinutes}
                  onChange={e => setForm({ ...form, intervalMinutes: Number(e.target.value) })} />
              </div>
            )}
            {form.kind === 'monitor' && (
              <div className="field">
                <label className="lbl">{t('auto.watch')}</label>
                <input className="input" dir="auto" value={form.conditionQuery} onChange={e => setForm({ ...form, conditionQuery: e.target.value })} />
                <div className="hint">{t('auto.watchHint')}</div>
              </div>
            )}
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button className="btn ghost" onClick={() => setShow(false)}>{t('common.cancel')}</button>
              <button className="btn" disabled={!form.title.trim()} onClick={create}>{t('auto.create')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
