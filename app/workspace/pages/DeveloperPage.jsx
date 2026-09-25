import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useI18n } from '../i18n/index.js';
import Icon from '../components/Icon.jsx';

// Browser-local developer sandbox. Real Git/terminal adapters are intentionally not claimed here.
export default function DeveloperPage({ onMenu }) {
  const { t } = useI18n();
  const [repos, setRepos] = useState([]);
  const [repo, setRepo] = useState(null);
  const [tree, setTree] = useState([]);
  const [active, setActive] = useState(null);
  const [text, setText] = useState('');
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState(null);
  const [diff, setDiff] = useState('');
  const [term, setTerm] = useState([]);
  const [cmd, setCmd] = useState('');
  const [checkpoints, setCheckpoints] = useState([]);
  const [newRepo, setNewRepo] = useState('');
  const [cloneUrl, setCloneUrl] = useState('');
  const [newFile, setNewFile] = useState('');
  const [q, setQ] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [gh, setGh] = useState(null);
  const [rail, setRail] = useState('terminal'); // terminal | diff | search | git | checkpoints

  const log = line => setTerm(v => [...v, line].slice(-400));

  const loadRepos = () => api.get('/dev/repos').then(setRepos).catch(() => {});
  useEffect(() => { loadRepos(); api.get('/dev/github/status').then(setGh).catch(() => {}); }, []);

  const openRepo = async name => {
    setRepo(name); setActive(null); setText(''); setSearchResults(null); setDiff(''); setRail('terminal'); setTerm([]);
    setTree(await api.get(`/dev/repos/${name}/tree`));
    setStatus(await api.get(`/dev/repos/${name}/status`));
    setCheckpoints(await api.get(`/dev/repos/${name}/checkpoints`));
  };

  const refresh = async () => {
    if (!repo) return;
    setTree(await api.get(`/dev/repos/${repo}/tree`));
    setStatus(await api.get(`/dev/repos/${repo}/status`));
    setCheckpoints(await api.get(`/dev/repos/${repo}/checkpoints`));
  };

  const openFile = async p => {
    const r = await api.get(`/dev/repos/${repo}/file?path=${encodeURIComponent(p)}`);
    setActive(p); setText(r.content); setDirty(false);
  };

  const save = async () => {
    if (!active) return;
    await api.put(`/dev/repos/${repo}/file`, { path: active, content: text });
    setDirty(false);
    log(`✓ ${t('dev.saved')} ${active}`);
    refresh();
  };

  const showDiff = async () => {
    setDiff((await api.get(`/dev/repos/${repo}/diff`)).diff || t('dev.noChanges'));
    setRail('diff');
  };

  const commit = async () => {
    const message = prompt(t('dev.commitMsg'), 'update');
    if (message === null) return;
    const r = await api.post(`/dev/repos/${repo}/commit`, { message });
    log(`✓ ${t('dev.committed')} ${r.sha.slice(0, 8)}`);
    refresh(); setDiff('');
  };

  const checkpoint = async () => {
    const label = prompt(t('dev.checkpointLabel'), t('dev.beforeChange'));
    if (label === null) return;
    const r = await api.post(`/dev/repos/${repo}/checkpoints`, { label });
    log(`✓ checkpoint ${r.id} @ ${r.sha.slice(0, 8)}`);
    refresh(); setRail('checkpoints');
  };

  const doRollback = async cp => {
    if (!confirm(t('dev.rollbackConfirm', { label: cp.label || cp.id }))) return;
    const r = await api.post(`/dev/repos/${repo}/rollback`, { checkpointId: cp.id });
    log(`✓ rollback -> ${r.head.slice(0, 8)} restored=${r.restored}`);
    setActive(null); setText(''); refresh();
  };

  const run = async () => {
    if (!cmd.trim()) return;
    log('$ ' + cmd);
    setRail('terminal');
    const c = cmd; setCmd('');
    try {
      const r = await api.post(`/dev/repos/${repo}/run`, { command: c });
      if (r.stdout) log(r.stdout);
      if (r.stderr) log('[stderr] ' + r.stderr);
      log(`(exit ${r.exitCode})`);
    } catch (e) { log('! ' + e.message); }
  };

  const doSearch = async () => {
    if (!q.trim()) return;
    setSearchResults(await api.get(`/dev/repos/${repo}/search?q=${encodeURIComponent(q)}`));
    setRail('search');
  };

  const createFile = async () => {
    const name = newFile.trim();
    if (!name) return;
    await api.put(`/dev/repos/${repo}/file`, { path: name, content: '' });
    setNewFile(''); refresh(); openFile(name);
  };

  // ---------- landing: repositories ----------
  if (!repo) {
    return (
      <>
        <div className="topbar">
          <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
          <h1>{t('dev.title')}</h1>
        </div>
        <div className="content narrow" style={{ maxWidth: 760 }}>
          <div className="card" style={{ marginBottom: 14 }}>
            <b>{t('dev.browserSandboxTitle')}</b>
            <p className="muted small" style={{ margin: '6px 0 0' }}>{t('dev.browserSandboxNotice')}</p>
          </div>
          <div className="card" style={{ marginBottom: 14 }}>
            <b>{t('dev.createOrClone')}</b>
            <div className="row" style={{ marginTop: 10 }}>
              <input className="input" placeholder="new-repo-name" value={newRepo} onChange={e => setNewRepo(e.target.value)}
                style={{ direction: 'ltr', textAlign: 'left' }} />
              <button className="btn" onClick={async () => { if (newRepo.trim()) { await api.post('/dev/repos', { name: newRepo.trim() }); setNewRepo(''); loadRepos(); } }}>{t('common.create')}</button>
            </div>
            <div className="row" style={{ marginTop: 8 }}>
              <input className="input" placeholder="https://github.com/user/repo.git" value={cloneUrl} onChange={e => setCloneUrl(e.target.value)}
                style={{ direction: 'ltr', textAlign: 'left' }} />
              <button className="btn ghost" onClick={async () => {
                if (!cloneUrl.trim()) return;
                const name = cloneUrl.split('/').pop().replace(/\.git$/, '');
                try { await api.post('/dev/repos', { cloneUrl: cloneUrl.trim(), name }); setCloneUrl(''); loadRepos(); }
                catch (e) { alert(e.message); }
              }}>{t('dev.clone')}</button>
            </div>
            {gh && !gh.configured && <p className="muted small" style={{ marginTop: 8 }}>{t('dev.ghHint')}</p>}
          </div>
          <div className="app-grid">
            {repos.map(r => (
              <button key={r.name} className="app-card click" style={{ textAlign: 'start', cursor: 'pointer' }} onClick={() => openRepo(r.name)}>
                <div className="row">
                  <span className="tic"><Icon name="git" size={18} /></span>
                  <b style={{ flex: 1 }}>{r.name}</b>
                  {r.dirty && <span className="tag warn">{t('dev.uncommitted')}</span>}
                </div>
                <div className="muted small" style={{ marginTop: 8, direction: 'ltr', textAlign: 'left' }}>
                  <Icon name="branch" size={12} /> {r.branch}
                </div>
              </button>
            ))}
            {repos.length === 0 && <div className="muted">{t('dev.noRepos')}</div>}
          </div>
        </div>
      </>
    );
  }

  // ---------- IDE shell ----------
  const RAIL_TABS = [
    ['terminal', t('dev.terminal'), 'terminal'],
    ['diff', t('dev.diff'), 'branch'],
    ['git', t('dev.gitState'), 'git'],
    ['checkpoints', t('dev.checkpoints'), 'history']
  ];

  return (
    <>
      <div className="topbar">
        <button className="iconbtn hamburger" aria-label="Menu" onClick={onMenu}><Icon name="menu" /></button>
        <button className="iconbtn" onClick={() => setRepo(null)}><Icon name="chevR" size={16} flip /></button>
        <h1 style={{ direction: 'ltr' }}>{repo}</h1>
        <span className="tag warn">{t('dev.localOnly')}</span>
        {status && <span className="tag"><Icon name="branch" size={11} /> {status.branch}</span>}
        <div className="spacer" />
        <button className="btn sm ghost" onClick={showDiff}>{t('dev.diff')}</button>
        <button className="btn sm ghost" onClick={checkpoint}>Checkpoint</button>
        <button className="btn sm ghost" onClick={commit}>{t('dev.commit')}</button>
        <button className="btn sm" onClick={save} disabled={!active || !dirty}>{t('common.save')}</button>
      </div>
      <div className="dev-shell">
        <div className="dev-side">
          <div className="dev-tools">
            <input className="input" style={{ fontSize: 12, direction: 'ltr', textAlign: 'left' }} placeholder={t('dev.searchCode')} value={q}
              onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && doSearch()} />
            <input className="input" style={{ fontSize: 12, direction: 'ltr', textAlign: 'left' }} placeholder="path/newfile.js" value={newFile}
              onChange={e => setNewFile(e.target.value)} onKeyDown={e => e.key === 'Enter' && createFile()} />
          </div>
          <div className="dev-tree" style={{ direction: 'ltr' }}>
            {tree.filter(f => f.type === 'file').map(f => (
              <button key={f.path} className={'tree-item' + (active === f.path ? ' active' : '')} onClick={() => openFile(f.path)}>
                <Icon name="file" size={13} /> {f.path}
              </button>
            ))}
          </div>
        </div>
        <div className="dev-main">
          <div className="dev-editorbar">
            <span className="fpath">{active || t('dev.selectFile')}{active && dirty ? ' •' : ''}</span>
          </div>
          <div className="dev-editor">
            <textarea value={active ? text : ''} placeholder={t('dev.selectFile')}
              onChange={e => { setText(e.target.value); setDirty(true); }} readOnly={!active} spellCheck={false} />
          </div>
          <div className="dev-rail">
            <div className="dev-rail-tabs">
              {RAIL_TABS.map(([id, label]) => (
                <button key={id} className={'rtab' + (rail === id ? ' on' : '')} onClick={async () => {
                  setRail(id);
                  if (id === 'diff' && !diff) setDiff((await api.get(`/dev/repos/${repo}/diff`)).diff || t('dev.noChanges'));
                  if (id === 'git') setStatus(await api.get(`/dev/repos/${repo}/status`));
                }}>{label}</button>
              ))}
              {searchResults && <button className={'rtab' + (rail === 'search' ? ' on' : '')} onClick={() => setRail('search')}>{t('dev.results')}</button>}
            </div>
            <div className="dev-rail-body">
              {rail === 'terminal' && <>
                <div className="term-out">{term.join('\n') || t('dev.termHint')}</div>
                <div className="term-line" style={{ marginTop: 8 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>$</span>
                  <input value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={e => e.key === 'Enter' && run()} placeholder="npm test" />
                </div>
              </>}
              {rail === 'diff' && <pre>{diff || t('dev.noChanges')}</pre>}
              {rail === 'git' && status && (
                <div style={{ direction: 'ltr', textAlign: 'left' }}>
                  <div className="row" style={{ marginBottom: 8 }}>
                    <span className="tag"><Icon name="branch" size={11} /> {status.branch}</span>
                    {status.dirty ? <span className="tag warn">{t('dev.uncommitted')}</span> : <span className="tag good">{t('dev.clean')}</span>}
                  </div>
                  {status.changes?.length > 0 && <pre>{status.changes.map(c => (c.status || '') + ' ' + (c.path || c)).join('\n')}</pre>}
                  {status.log && <pre>{status.log}</pre>}
                </div>
              )}
              {rail === 'checkpoints' && (
                <div>
                  {checkpoints.length === 0 && <div className="muted small">{t('dev.noCheckpoints')}</div>}
                  {checkpoints.map(cp => (
                    <div key={cp.id} className="run-row" style={{ direction: 'ltr' }}>
                      <Icon name="history" size={13} />
                      <span style={{ flex: 1 }}>{cp.label || cp.id} <span className="muted">{cp.git_ref.slice(0, 8)}</span></span>
                      <button className="btn sm ghost" onClick={() => doRollback(cp)}>{t('dev.rollback')}</button>
                    </div>
                  ))}
                </div>
              )}
              {rail === 'search' && searchResults && (
                <div style={{ direction: 'ltr', textAlign: 'left' }}>
                  {searchResults.map((r, i) => (
                    <button key={i} className="tree-item" onClick={() => openFile(r.file)}>
                      {r.file}:{r.line} — <code style={{ fontSize: 11.5 }}>{r.text}</code>
                    </button>
                  ))}
                  {searchResults.length === 0 && <p className="muted small">{t('search.noResults')}</p>}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
