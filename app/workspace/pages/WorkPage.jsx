import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from '../router.js';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.js';
import Icon from '../components/Icon.jsx';

// User-facing task types → wire contract (kind/format). Internal ids never shown.
const TYPES = [
  { id: 'doc', kind: 'work.deliverable', format: 'pdf', tKey: 'work.type.doc' },
  { id: 'sheet', kind: 'work.deliverable', format: 'xlsx', tKey: 'work.type.sheet' },
  { id: 'deck', kind: 'work.deliverable', format: 'pptx', tKey: 'work.type.deck' },
  { id: 'md', kind: 'work.deliverable', format: 'md', tKey: 'work.type.md' },
  { id: 'research', kind: 'research.deep', format: 'md', tKey: 'work.type.research' }
];

const STEP_KEY = name => {
  if (name.startsWith('search')) return 'step.search';
  const map = { persist: 'step.persist', plan: 'step.plan', generate: 'step.generate', render: 'step.render', verify: 'step.verify', synthesize: 'step.synthesize' };
  return map[name] || null;
};

function StatusTag({ status, t }) {
  const map = {
    done: ['good', 'work.done'], failed: ['bad', 'work.failed'], cancelled: ['bad', 'work.cancelled'],
    running: ['acc', 'work.running'], claimed: ['acc', 'work.running'], queued: ['', 'work.queued']
  };
  const [cls, key] = map[status] || ['', 'work.queued'];
  return <span className={'tag ' + cls}>{t(key)}</span>;
}

export default function WorkPage({ onMenu }) {
  const { id } = useParams();
  const nav = useNavigate();
  const { t } = useI18n();
  const [jobs, setJobs] = useState([]);
  const [detail, setDetail] = useState(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ prompt: '', type: 'doc' });

  const load = useCallback(() => {
    api.get('/jobs').then(setJobs).catch(() => {});
    if (id) api.get('/jobs/' + id).then(setDetail).catch(() => nav('/work'));
  }, [id]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 2500);
    return () => clearInterval(timer);
  }, [load]);

  const create = async () => {
    if (!form.prompt.trim()) return;
    const tp = TYPES.find(x => x.id === form.type);
    const title = form.prompt.trim().slice(0, 60);
    const j = await api.post('/jobs', {
      title, kind: tp.kind, format: tp.format,
      prompt: form.prompt, question: form.prompt, goal: form.prompt, iterations: 3
    });
    setShow(false); setForm({ prompt: '', type: 'doc' });
    nav('/work/' + j.id);
  };

  const parseResult = j => { try { return JSON.parse(j.result || 'null'); } catch { return null; } };
  const objectiveOf = j => { try { const i = JSON.parse(j.input || '{}'); return i.prompt || i.question || i.goal || j.title; } catch { return j.title; } };

  // ---------- detail view ----------
  if (id && detail) {
    const res = parseResult(detail);
    const steps = detail.steps || [];
    const evidence = detail.evidence || [];
    const running = ['running', 'queued', 'claimed'].includes(detail.status);
    return (
      <>
        <div className="topbar">
          <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
          <button className="iconbtn" onClick={() => nav('/work')}><Icon name="chevR" size={16} flip /></button>
          <h1>{detail.title}</h1>
          <StatusTag status={detail.status} t={t} />
          {running && <button className="btn sm ghost" onClick={async () => { await api.post(`/jobs/${detail.id}/cancel`); load(); }}>{t('work.cancel')}</button>}
          {(detail.status === 'failed' || detail.status === 'cancelled') && (
            <button className="btn sm" onClick={async () => { await api.post(`/jobs/${detail.id}/retry`); load(); }}>{t('work.retryTask')}</button>
          )}
        </div>
        <div className="content narrow" style={{ maxWidth: 760 }}>
          <div className="card" style={{ marginBottom: 14 }}>
            <div className="muted small" style={{ marginBottom: 4 }}>{t('work.objective')}</div>
            <div dir="auto">{objectiveOf(detail)}</div>
          </div>

          <div className="card" style={{ marginBottom: 14 }}>
            <div className="muted small" style={{ marginBottom: 10 }}>{t('work.activity')}</div>
            <div className="timeline">
              {steps.map((s, i) => {
                const key = STEP_KEY(s.step || s.name || '');
                return (
                  <div key={i} className={'tstep ' + (s.status === 'done' ? 'done' : s.status === 'failed' ? 'failed' : running && i === steps.length - 1 ? 'running' : '')}>
                    <div className="tname">{key ? t(key) : s.name}</div>
                    {s.detail && <div className="tsub">{String(s.detail).slice(0, 140)}</div>}
                  </div>
                );
              })}
              {steps.length === 0 && <div className="muted small">{t('common.loading')}</div>}
            </div>
          </div>

          {evidence.length > 0 && (
            <div className="card" style={{ marginBottom: 14 }}>
              <div className="muted small" style={{ marginBottom: 8 }}>{t('work.sources')}</div>
              <div className="sources-row">
                {evidence.filter(e => e.url).map((e, i) => (
                  <a key={i} className="src-chip" href={e.url} target="_blank" rel="noreferrer">
                    <span className="n">{i + 1}</span> {e.title || (() => { try { return new URL(e.url).hostname; } catch { return e.url; } })()}
                  </a>
                ))}
              </div>
            </div>
          )}

          {res?.fileId && (
            <div className="card" style={{ marginBottom: 14 }}>
              <div className="muted small" style={{ marginBottom: 8 }}>{t('work.result')}</div>
              <a className="artifact-card" href={api.fileUrl(res.fileId)} target="_blank" rel="noreferrer" style={{ textDecoration: 'none', color: 'inherit' }}>
                <span className="fic"><Icon name="file" size={18} /></span>
                <span className="fmeta">
                  <span className="fname">{detail.title}.{res.format || 'file'}</span>
                  <span className="fsize">{t('work.openResult')}</span>
                </span>
                <Icon name="download" size={16} />
              </a>
            </div>
          )}

          <details className="disclosure">
            <summary>{t('work.details')}</summary>
            <pre>{JSON.stringify({ id: detail.id, kind: detail.kind, status: detail.status, steps: steps.map(s => ({ step: s.step, status: s.status })) }, null, 2)}</pre>
          </details>
        </div>
      </>
    );
  }

  // ---------- list view ----------
  return (
    <>
      <div className="topbar">
        <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
        <h1>{t('work.title')}</h1>
        <button className="btn" onClick={() => setShow(true)}><Icon name="plus" size={15} /> {t('work.newTask')}</button>
      </div>
      <div className="content narrow" style={{ maxWidth: 760 }}>
        {jobs.length === 0 && (
          <div className="empty">
            <Icon name="work" size={28} />
            <p>{t('work.empty')}</p>
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {jobs.map(j => (
            <button key={j.id} className="card click task-card" onClick={() => nav('/work/' + j.id)} style={{ textAlign: 'start', width: '100%' }}>
              <span className="tmeta">
                <span className="tname" dir="auto">{j.title}</span>
                <span className="tsub" dir="auto">{objectiveOf(j).slice(0, 90)}</span>
              </span>
              <StatusTag status={j.status} t={t} />
            </button>
          ))}
        </div>
      </div>

      {show && (
        <div className="modal-backdrop" onClick={() => setShow(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>{t('work.newTask')}</h3>
            <div className="field">
              <label className="lbl">{t('work.objective')}</label>
              <textarea className="input" rows={4} dir="auto" autoFocus value={form.prompt}
                onChange={e => setForm({ ...form, prompt: e.target.value })} />
            </div>
            <div className="field">
              <label className="lbl">{t('work.type')}</label>
              <div className="row">
                {TYPES.map(tp => (
                  <button key={tp.id} className={'chip' + (form.type === tp.id ? ' on' : '')}
                    onClick={() => setForm({ ...form, type: tp.id })}>{t(tp.tKey)}</button>
                ))}
              </div>
            </div>
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button className="btn ghost" onClick={() => setShow(false)}>{t('common.cancel')}</button>
              <button className="btn" disabled={!form.prompt.trim()} onClick={create}>{t('work.start')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
